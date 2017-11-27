.. _config-file:

Perun Configuration files
=========================

.. _Yaml: http://yaml.org/

Perun stores its configuration in Yaml_ format, either locally for each wrapped repository, or
globally for the whole system (see :ref:`config-types`). Most of the configuration options is
recursively looked up in the hierarchy, created by local and global configurations, until the
option is found in the nearest configuration. Refer to :ref:`config-options` for description
of options, such as formatting strings for status and log outputs, specification of job matrix (in
more details described in :ref:`jobs-matrix`) or information about wrapped repository.

In order to configure your local instance of Perun run the following::

    perun config --edit

This will open the nearest local configuration in text editor (by default in ``vim``) and lets you
modify the options w.r.t. Yaml_ format.

.. _config-types:

Configuration types
-------------------

Perun uses two types of configurations: **global**  and **local**. The global configuration
contains options shared by all of the Perun instances found on the host and the local configuration
corresponds to concrete wrapped repositories (which can, obviously, be of different type, with
different projects and different profiling information). Both global and local configurations have
several options restricted only to their type (which is emphasized in the description of individual
option). The rest of the options can then be looked up recursively (i.e. first we check the nearest
local perun instance, until we find the searched option or eventually end up in the global
configuration). Options are specified by configuration sections, subsections and then concrete
options delimited by ``.``, e.g.  ``local.global.editor`` corresponds to the ``editor`` option in
the ``global`` section in ``local`` configuration.

The location of global configuration differs according to the host system. In UNIX systems, the
**global** configuration can be found at::

    $HOME/.config/perun

In Windows systems it is located in user storage::

    %USERPROFILE%\AppData\Local\perun

.. _config-options:

List of Supported Options
-------------------------

.. confunit:: vcs

    ``[local-only]`` Section, which contains options corresponding to the version control system
    that is wrapped by instance of Perun. Specifies e.g. the type (in order to call corresponding
    auxiliary functions), the location in the filesystem or wrapper specific options (e.g. the
    lightweight custom ``tagit`` vcs constains additional options).

.. confkey:: vcs.type

    ``[local-only]`` Specifies the type of the wrapped version control system, in order to call
    corresponding auxiliary functions. Currently ``git`` is supported, with custom lightweight vcs
    ``tagit`` in development.

.. confkey:: vcs.url

    ``[local-only]`` Specifies path to the wrapped version control system, either as an absolute or
    a relative path that leads to the directory, where the root of the wrapped repository is (e.g.
    where ``.git`` is).

.. confunit:: global

    Section, which contains options and specifications potentially shared by more Perun instances.
    This section contains e.g. formatting specifications for ``perun log`` and ``perun status``,
    underlying text editor for editing, etc.

.. confkey:: global.paging

.. todo::
    To be done both in implementation and here in documentation :P

.. confkey:: global.editor

    ``[recursive]`` Sets user choice of text editor, that is e.g. used for manual text-editing of
    configuration files of Perun. Specified editor needs to be executable, has to take the filename
    as an argument and will be called as ``global.editor config.yml``. By default :ckey:`editor` is
    set to ``vim``.

.. confkey:: global.profile_info_fmt

    ``[recursive]`` Specifies the formatting string for the output of the ``perun status`` command.
    The formatting string can contain raw delimiters and special tags, which are used to output
    concrete information about each profile, like e.g. command it corresponds to, type of the
    profile, time of creation, etc. Refer to :ref:`logs-status` for more information regarding the
    formatting strings for ``perun status``.

    E.g. the following formatting string::

         ┃ [type] ┃ [cmd] ┃ [workload] ┃ [collector]  ┃ ([time]) ┃

    will yield the following status when running ``perun status`` (both for stored and pending
    profiles)::

        ═══════════════════════════════════════════════════════════════════════════════▣
          id ┃   type  ┃  cmd   ┃ workload ┃  args  ┃ collector  ┃         time        ┃
        ═══════════════════════════════════════════════════════════════════════════════▣
         0@p ┃ [mixed] ┃ target ┃ hello    ┃        ┃ complexity ┃ 2017-09-07 14:41:49 ┃
         1@p ┃ [time ] ┃ perun  ┃          ┃ status ┃ time       ┃ 2017-10-19 12:30:29 ┃
         2@p ┃ [time ] ┃ perun  ┃          ┃ --help ┃ time       ┃ 2017-10-19 12:30:31 ┃
        ═══════════════════════════════════════════════════════════════════════════════▣

.. confkey:: global.minor_version_info_fmt

    ``[recursive]`` Specifies the formatting string for the output of the short format of ``perun
    log`` command. The formatting string can contain raw characters (delimiters, etc.) and special
    tags, which are used to output information about concrete minor version (e.g. minor version
    description, number of assigned profiles, etc.). Refer to :ref:`logs-log` for more information
    regarding the formatting strings for ``perun log``.

    E.g. the following formatting string::

        '[id:6] ([stats]) [desc]'

    will yield the following output when running ``perun log --short``::

        minor   (a|m|x|t profiles) info
        53d35c  (2|0|2|0 profiles) Add deleted jobs directory
        07f2b4  (1|0|1|0 profiles) Add necessary files for perun to work on this repo.
        bd3dc3  ---no--profiles--- root

.. confkey:: cmds

    ``[local-only]`` Refer to :munit:`cmds`. 

.. confkey:: args

    ``[local-only]`` Refer to :munit:`args`.

.. confkey:: workloads

    ``[local-only]`` Refer to :munit:`workloads`

.. confkey:: collectors

    ``[local-only]`` Refer to :munit:`collectors`

.. confkey:: postprocessors

    ``[local-only]`` Refer to :munit:`postprocessors`

.. _config-cli:

Command Line Interface
----------------------

We advise to manipulate with configurations using the ``perun config --edit`` command. In order to
change the nearest local (resp. global) configuration run ``perun config --local --edit`` (resp.
``perun config --shared --edit``).

.. click:: perun.cli:config
   :prog: perun config
