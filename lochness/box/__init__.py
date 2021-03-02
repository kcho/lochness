import os
import gzip
import dropbox
import logging
import importlib
import boxsdk
import tempfile as tf
import cryptease as crypt
import lochness.net as net
from typing import Generator, Tuple
from pathlib import Path
# from . import hash as hash

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024

def delete_on_success(Lochness, module_name):
    ''' get module-specific delete_on_success flag with a safe default '''
    value = Lochness.get('box', dict()) \
                    .get(module_name, dict()) \
                    .get('delete_on_success', False)
    # if this is anything but a boolean, just return False
    if not isinstance(value, bool):
        return False
    return value


def base(Lochness, module_name):
    ''' get module-specific base box diretory '''
    return Lochness.get('box', {}) \
                   .get(module_name, {}) \
                   .get('base', '')


@net.retry(max_attempts=5)
def sync(Lochness, subject, dry):
    '''call sync on the correct sub-module'''
    for module in subject.box:
        get(module).sync(Lochness, subject, dry)


def get(module):
    '''return a specific box module'''
    try:
        module = '.' + module
        return importlib.import_module(module, 'lochness')
    except ImportError:
        msg = f'no module {module} in package lochness.box'
        raise ImportError(msg)


def get_box_object_based_on_name(client:boxsdk.client,
                               box_folder_name: str,
                               box_path_id: str = '0') -> boxsdk.object.folder:
    '''Return Box folder object for the given folder name

    Currently, there is no api function to get box folder objects using
    path strings in Box.
        - https://stackoverflow.com/questions/16153409/is-there-any-easy-way-to-get-folderid-based-on-a-given-path

    This function will recursively search for a folder which
    has the same name as the `bx_head` and return its id.

    Key Arguments:
        client: Box client object
        box_folder_name: Name of the folder in interest, str
        box_path: Known parent id, str of int.
                  Default=0. This execute search from the root.

    Returns:
        box_folder_object
    '''
    box_folder_name = str(box_folder_name)

    # get list of files and directories under the top directory
    root_dir = client.folder(folder_id=box_path_id).get()

    # for entry in listing.entries:
    for file_or_folder in root_dir.get_items():
        if file_or_folder.type == 'folder' and \
           file_or_folder.name == box_folder_name:
            return file_or_folder


def walk_from_folder_object(root: str, box_folder_object) -> \
        Generator[str, list, list]:
    '''top-down os.path.walk that operates on a Box folder object

    Box does not support getting files with path strings.

    Key Arguments:
        root: path of the folder, str
        box_folder_object: folder object, Box Folder

    Yields:
        (root, box_folder_objects, box_file_object)
        root: root of the following objects, str
        box_folder_object: box folder objects, list
        box_file_object: box file objects, list
    '''
    box_folder_objects, box_file_objects = [], []
    # for entry in listing.entries:
    for file_or_folder in box_folder_object.get_items():
        if file_or_folder.type == 'folder':
            box_folder_objects.append(file_or_folder)
        else:
            box_file_objects.append(file_or_folder)

    yield root, box_folder_objects, box_file_objects

    for box_dir_object in box_folder_objects:
        new_root = os.path.join(root, box_dir_object.name)
        for x in walk_from_folder_object(new_root, box_dir_object):
            yield x


def save(box_file_object: boxsdk.object.file,
         box_path_tuple: Tuple[str, str],
         out_base: str,
         key=None,
         compress=False, delete=False, dry=False):
    '''save a box file to an output directory'''
    # file path
    box_path_root, box_path_name = box_path_tuple
    box_fullpath = os.path.join(box_path_root, box_path_name)

    # extension
    ext = '.lock' if key else ''
    ext = ext + '.gz' if compress else ext

    # local path
    local_fullfile = os.path.join(out_base, box_path_name + ext)

    if os.path.exists(local_fullfile):
        return
    local_dirname = os.path.dirname(local_fullfile)
    if not os.path.exists(local_dirname):
        os.makedirs(local_dirname)

    if not dry:
        try:
            _save(box_file_object, box_fullpath, local_fullfile, key, compress)
            if delete:
                logger.debug(f'deleting file on box {box_fullpath}')
                _delete(box_file_object, box_fullpath)
        except HashRetryError:
            msg = f'too many failed attempts downloading {box_fullpath}'
            raise DownloadError(msg)


def hash_retry(n):
    '''decorator to retry a box download on hash mismatch'''
    def wrapped(func):
        def f(*args, **kwargs):
            attempts = 1
            while attempts <= n:
                try:
                    return func(*args, **kwargs)
                except BoxHashError as e:
                    msg = f'attempt {attempts}/{n} failed with error: {e}'
                    logger.warn(msg)
                    attempts += 1
                    os.remove(e.filename)
            raise HashRetryError()
        return f
    return wrapped


class HashRetryError(Exception):
    pass


def _delete(box_file_object: boxsdk.object.file, box_fullpath: str):
    try:
        md = box_file_object.delete()
    except dropbox.exceptions.ApiError as e:
        raise DeletionError(f'error deleting file {box_fullpath}')


class DeletionError(Exception):
    pass


@hash_retry(3)
def _save(box_file_object, box_fullpath, local_fullfile, key, compress):
    # request the file from box.com
    try:
        # md, resp = client.files_download(box_fullpath)
        # content = client.file(file_id).content()
        content = box_file_object.content()
    except dropbox.exceptions.ApiError as e:
        if e.error.is_path() and e.error.get_path().is_not_found():
            msg = f'error downloading file {box_fullpath}'
            raise DownloadError(msg)
        else:
            raise e
    local_dirname = os.path.dirname(local_fullfile)
    logger.info(f'saving {box_fullpath} to {local_fullfile} ')

    # write the file content to a temporary location
    if key:
        _stream = crypt.encrypt(content, key, chunk_size=CHUNK_SIZE)
        tmp_name = _savetemp(content, local_dirname, compress=compress)
        # tmp_name = _savetemp(crypt.buffer(_stream),
                             # local_dirname,
                             # compress=compress)
    else:
        tmp_name = _savetemp(content, local_dirname, compress=compress)

    # verify the file and rename to final local destination
    logger.debug(f'verifying temporary file {tmp_name}')
    # verify(tmp_name, md.content_hash, key=key, compress=compress)
    os.chmod(tmp_name, 0o0644)
    os.rename(tmp_name, local_fullfile)


class DownloadError(Exception):
    pass


def _savetemp(content, dirname=None, compress=False):
    '''save content to a temporary file with optional compression'''
    if not dirname:
        dirname = tf.gettempdir()
    fo = tf.NamedTemporaryFile(dir=dirname, prefix='.', delete=False)
    if compress:
        fo = gzip.GzipFile(fileobj=fo, mode='wb')

    # while 1:
        # buf = content.read(CHUNK_SIZE)
        # if not buf:
            # break
    fo.write(content)

    fo.flush()
    os.fsync(fo.fileno())
    fo.close()
    return fo.name


def verify(f, content_hash, key=None, compress=False):
    '''compute dropboxbox hash of a local file and compare to content_hash'''
    hasher = hash.DropboxContentHasher()
    fo = open(f, 'rb')
    if compress:
        fo = gzip.GzipFile(fileobj=fo, mode='rb')
    if key:
        fo = crypt.buffer(crypt.decrypt(fo, key, chunk_size=CHUNK_SIZE))
    while 1:
        buf = fo.read(CHUNK_SIZE)
        if not buf:
            break
        hasher.update(buf)
    fo.close()
    if hasher.hexdigest() != content_hash:
        message = f'hash mismatch detected for {f}'
        raise BoxHashError(message, f)


class BoxHashError(Exception):
    def __init__(self, message, filename):
        super(BoxHashError, self).__init__(message)
        self.filename = filename
