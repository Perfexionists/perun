.. _config-file:

Perun Configuration files
=========================

Perun specifies its configurations options in YAML format, either locally for each wrapped
repository, or globally for the whole system (see :ref:`config-types`). Most of the options are
recursively looked up until the option is found in the nearest Perun configuration.
:ref:`config-options` consist e.g. of formatting strings for status and log outputs, specification
of job matrix (in more details described in :ref:`jobs-matrix`) or information about wrapped
repository.

.. _config-types:

Configuration types
-------------------

In Perun there are two types of configurations **global** (or **shared**) and **local**, where the
first one contains options available to all of the Perun systems found on the host, and the other
correspond to concrete wrapped repositories (which can be of different type, with different projects
and different profiling information). Several options are restricted to global or local
configurations (which is specified in the description), the rest of the options can be looked up
recursively (i.e. first we check the nearest local perun directory, until we find the specified
option or end in the global configuration). The specification of configuration sections, subsections
and concrete options is delimited by ``.``, e.g. ``shared.global.editor`` corresponds to the
``editor`` option in the ``global`` section in ``shared`` configuration.

In UNIX systems, the **global** configuration can be found at::

    $HOME/.config/perun

In Windows systems, the **global** configuration can be found at::

    %USERPROFILE%\AppData\Local\perun

.. _config-options:

List of Supported Options
-------------------------

.. confunit:: vcs

    !Only in local configuration! Contains information about wrapped Version Control System, its
    type and the location in the filesystem.

.. confkey:: type

    Type of the wrapped Version Control System, currently one of (``git``)

.. confkey:: url

    Path to the wrapped Version Control System, contains either absolute or relative path
    that leads to the directory, where the root of the wrapped repository is (e.g. where ``.git``
    is).

.. confunit:: global

    Contains set of global options and specifications for Perun. Currently this contains formatting
    specifications for ``perun log`` and ``perun status``, editor, etc.

.. confkey:: paging

.. todo::
    To be done both in implementation and here in documentation :P

.. confkey:: editor

    User choice of editor, used for manual text-editing configuration files of Perun. Specified
    editor has to take the filename as an argument. By default :ckey:`editor` is set to ``vim``.

.. confkey:: global.profile_info_fmt

    Specification of formatting string for output of ``perun status``. The format consists of raw
    delimiters and files and special tags, which can be used to output concrete information about
    profiles, like e.g. its commands, types, time, etc. See :ref:`logs-format` for more information
    regarding the formatting strings for ``perun status``.

    E.g. the following formatting string::

         ┃ [type] ┃ [cmd] ┃ [workload] ┃ [collector]  ┃ ([time]) ┃ [id] ┃

    will yield the following status by running ``perun status`` (both for stored and pending
    profiles::

        ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════▣
          id ┃   type  ┃  cmd   ┃ workload ┃  args  ┃ collector  ┃         time        ┃                        id                        ┃
        ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════▣
         0@p ┃ [mixed] ┃ target ┃ hello    ┃        ┃ complexity ┃ 2017-09-07 14:41:49 ┃ .perun/jobs/big.perf                             ┃
         1@p ┃ [time ] ┃ perun  ┃          ┃ status ┃ time       ┃ 2017-10-19 12:30:29 ┃ .perun/jobs/perun-time--2017-10-19-10-30-29.perf ┃
         2@p ┃ [time ] ┃ perun  ┃          ┃ --help ┃ time       ┃ 2017-10-19 12:30:31 ┃ .perun/jobs/perun-time--2017-10-19-10-30-30.perf ┃
        ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════▣

.. confkey:: global.minor_version_info_fmt

    :ckey:`global.minor_version_info_fmt` serves as a formatting string for short format of ``perun
    log`` to display both raw information (delimiters, etc.) and information about minor version
    (e.g. minor version description, number of assigned profiles, etc.). See :ref:`logs-format` for
    more information regarding the formatting strings for ``perun log``.

    E.g. the following formatting string::

        '[id:6] ([stats]) [desc]'

    will yield the following output by running ``perun log --short``::

        minor   (a|m|x|t profiles) info
        53d35c  (2|0|2|0 profiles) Add deleted jobs directory
        07f2b4  (1|0|1|0 profiles) Add necessary files for perun to work on this repo.
        bd3dc3  ---no--profiles--- root

.. todo::
    Add matrix specific stuff here

.. todo::
    Fix the wrong high-lighting

.. todo::
    Add specifications which keys are global/shared/looked-up-recursively

.. _config-cli:

Command Line Interface
----------------------

.. click:: perun.cli:config
   :prog: perun config
