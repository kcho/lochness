Configuration file
==================
The folling page will go over all of the configuration file sections, fields, 
and what each one does

keyring_file
------------
This field specifies the location of your ``keyring`` file. This should be 
a simple filesystem location ::

    keyring_file: ~/.keyring.enc


phoenix_root
------------
This field determines the root location of your PHOENIX filesystem. This 
should be a simple filesystem location ::

    phoenix_root: /data/PHOENIX

stdout
------
This field determines the location of the Lochness process standard output

    stdout: /logs/lochness.out

stderr
------
This field determines the location of the Lochness process standard error

    stderr: /logs/lochness.err

poll_interval
-------------
This field determines the frequency at which Lochness will poll external data
sources for incoming data (in seconds)

    poll_interval: 43200

beiwe
-----
The ``beiwe`` section is used to configure how Lochness will behave while downloading
data from the `Beiwe <https://beiwe.org>`_.

backfill_start
~~~~~~~~~~~~~~
The ``backfill_start`` field should be an ISO 8601 formatted timestamp.  If you do not 
add a ``backfill_start`` date, the start date will fall back to the date that Beiwe 
was initially released ::

    2015-10-01T00:00:00

If you set the ``backfill_start`` field to the string ``consent``, Lochness will use 
the subject ``Consent Date`` from the PHOENIX `metadata file <phoenix.html#metadata-files>`_
as the backfill starting point.

A valid ``backfill_start`` field should look like this ::

    beiwe:
      backfill_start: consent

or like this ::

    beiwe:
      backfill_start: 2020-01-01

dropbox
-------
The ``dropbox`` section is used to configure how Lochness will behave when 
downloading data from `Dropbox <https://dropbox.com>`_.

delete on success
~~~~~~~~~~~~~~~~~
You can add a ``delete_on_success: True`` field to indicate that any data successfully
downloaded from a specific Dropbox account should be subsequently deleted from Dropbox 
to save space. You can configure ``delete_on_success`` for each Dropbox account defined 
in your ``keyring``. 

The resulting section should look as follows ::

    dropbox:
      example:
        delete_on_success: True

dropbox base
~~~~~~~~~~~~
For each Dropbox account, you may add a ``base`` field to the configuration file to 
indicate that Lochness should begin searching Dropbox starting at that location. 

The resulting section should look as follows ::

    dropbox:
      example:
        base: /PHOENIX

redcap
------
For each PHOENIX study, you may add an entry to the ``redcap`` section indicating 
that data should be de-identified before being downloaded and saved to PHOENIX.

Assuming your PHOENIX study is named ``StudyA`` this field would look like so ::

    redcap:
      StudyA:
        deidentify: True

admins
------
All email addresses defined in the ``admins`` section will be notified on all emails 
sent out by Lochness ::

    admins:
     username@email.com

notify
------
The ``notify`` section allows you to configure more detailed notification behavior. 
You can use this section to set different groups of email addresses to be notified 
in the event of an error downloading files on a per study basis ::

     notify:
      StudyA:
        - username1@email.com
        - username2@email.com
      StudyB:
        - username3@email.com

You can also use a ``__global__`` field to add email addresses that should be 
notified on any error for any study, similar to the `admins <#admins>`_ 
section ::

    notify:
      __global__:
        - admin1@email.com

sender
------
Whenever an email is sent by Lochness, use this field to determine the sender
address ::

    sender: lochness@host.example.org

ssh_user
--------
Occasionally, you may receive data on an external hard drive or flash drive.
If you want to use Lochness to transfer this data to your PHOENIX filesystem,
you can do this over ``rsync+ssh``. The ``ssh_user`` field determines the
username that will be used for this ::

    ssh_user: example

ssh_host
--------
Occasionally, you may receive data on an external hard drive or flash drive.
If you want to use Lochness to transfer this data to your PHOENIXfilesystem,
you can do this over ``rsync+ssh``. The ``ssh_host`` field determines the
destination host you will connect to for this ::

    ssh_host: host.example.org

