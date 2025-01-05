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
option). The rest of the options can then be looked up either recursively (i.e. first we check the
nearest local perun instance, and traverse to higher instances until we find the searched option or
eventually end up in the global configuration) or gathered from all of the configurations from the
whole configuration hierarchy (ordered by the depth of the hierarchy, i.e. options found in global
configuration will be on the bottom of the list). Options are specified by configuration sections,
subsections and then concrete options delimited by ``.``, e.g.  ``local.general.editor``
corresponds to the ``editor`` option in the ``general`` section in ``local`` configuration.

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

.. confunit:: general

    Section, which contains options and specifications potentially shared by more Perun instances.
    This section contains e.g. underlying text editor for editing, or paging strategy etc.

.. confkey:: general.paging

    Sets the paging for ``perun log`` and ``perun status``. Paging can be currently set to the
    following four options: ``always`` (both ``log`` and ``status`` will be paged), ``only-log``
    (only output of ``log`` will be paged), ``only-status`` (only output of ``status`` will be
    paged and ``never``. By default ``only-log`` is used in the configuration. The behaviour of
    paging can be overwritten by option ``--no-pager`` (see :doc:`cli`).

.. confkey:: general.editor

    ``[recursive]`` Sets user choice of text editor, that is e.g. used for manual text-editing of
    configuration files of Perun. Specified editor needs to be executable, has to take the filename
    as an argument and will be called as ``general.editor config.yml``. 
    By default :ckey:`general.editor` is set to ``vim``.

.. confunit:: format

    This section contains various formatting specifications e.g. formatting specifications for
    ``perun log`` and ``perun status``.

.. confkey:: format.status

    ``[recursive]`` Specifies the formatting string for the output of the ``perun status`` command.
    The formatting string can contain raw delimiters and special tags, which are used to output
    concrete information about each profile, like e.g. command it corresponds to, type of the
    profile, time of creation, etc. Refer to :ref:`logs-status` for more information regarding the
    formatting strings for ``perun status``.

    E.g. the following formatting string::

         ┃ %type% ┃ %cmd% ┃ %workload% ┃ %collector%  ┃ (%time%) ┃

    will yield the following status when running ``perun status`` (both for stored and pending
    profiles)::

        ══════════════════════════════════════════════════════════════════════▣
          id ┃   type  ┃  cmd   ┃ workload ┃ collector  ┃         time        ┃
        ══════════════════════════════════════════════════════════════════════▣
         0@p ┃ [mixed] ┃ target ┃ hello    ┃ complexity ┃ 2017-09-07 14:41:49 ┃
         1@p ┃ [time ] ┃ perun  ┃ status   ┃ time       ┃ 2017-10-19 12:30:29 ┃
         2@p ┃ [time ] ┃ perun  ┃ --help   ┃ time       ┃ 2017-10-19 12:30:31 ┃
        ══════════════════════════════════════════════════════════════════════▣

.. confkey:: format.shortlog

    ``[recursive]`` Specifies the formatting string for the output of the short format of ``perun
    log`` command. The formatting string can contain raw characters (delimiters, etc.) and special
    tags, which are used to output information about concrete minor version (e.g. minor version
    description, number of assigned profiles, etc.). Refer to :ref:`logs-log` for more information
    regarding the formatting strings for ``perun log``.

    E.g. the following formatting string::

        '%id:6% (%stats%) %desc%'

    will yield the following output when running ``perun log --short``::

        minor   (a|m|x|t profiles) info
        53d35c  (2|0|2|0 profiles) Add deleted jobs directory
        07f2b4  (1|0|1|0 profiles) Add necessary files for perun to work on this repo.
        bd3dc3  ---no--profiles--- root

.. confkey:: format.output_profile_template

    ``[recursive]`` Specifies the format for automatic generation of profile files (e.g. when
    running ``perun run job``, ``perun run matrix``, ``perun collect`` or ``perun postprocessby``.
    The formatting string consists either of raw characters or special tags, that output
    information according to the resulting profile. By default the following formatting string is
    set in the global configuration::

        "%collector%-%cmd%-%workload%-%date%"

    The supported tags are as follows:

    ``%collector%``:

        Placeholder for the collection unit that collected the profiling data of the given profile.
        Refer to :ref:`collectors-list` for full list of supported collectors.

    ``%postprocessors%``:

        Placeholder for list of postprocessors that were used on the given profile. The resulting
        string consists of postprocessor names joined by ``-and-`` string, i.e. for example this will
        output string ``regressogram-and-regression-analysis``.

    ``%<unit>.<param>%``:

        Placeholder for concrete value of ``<param>`` of one unit ``<unit>`` (either collector or
        postprocessor)

    ``%cmd%``:

        Placeholder for the command that was profiled, i.e. some binary, script or command (refer
        to :munit:`cmds` or :doc:`jobs` for more details).

    ``%workload%``:

        Placeholder for workload that was supplied to the profiled command (refer to
        :munit:`workloads` or :doc:`jobs` for more details).

    ``%label%``:

        Placeholder for custom user-supplied string label associated with a profile.

    ``%type%``:

        Placeholder for global type of the resources of the profile, i.e. `memory`, `time`,
        `mixed`, etc.

    ``%date%``:

        Placeholder for the time and date that the profile was generated in form of
        ``YEAR-MONTH-DAY-HOUR-MINUTES-SECONDS``.

    ``%origin%``:

        Placeholder for the origin of the profile, i.e. the minor version identification for which
        the profiles was generated and the profiling data was collected.

    ``%counter%``:

        Placeholder for increasing counter (counting from 0) for one run of perun. Note that this
        may rewrite existing profiles and is mostly meant to distinguish between profiles during
        one batch run of profile generation (e.g. when ``perun run matrix`` is executed).

.. confkey:: format.sort_profiles_by

    ``[recursive]`` Specifies which key of the profile will be used for sorting the output of the
    ``perun status`` commands. Can be one of the following attributes specified by the class
    attribute ``ProfileInfo.valid_attributes``:

.. currentmodule:: perun.profile.helpers
.. autoattribute:: ProfileInfo.valid_attributes

.. confkey:: format.sort_profiles_order

    ``[recursive]`` Specifies the order which will be used for sorting the output of the
    ``perun status`` commands. Can be either ``ascending`` or ``descending``.

.. confunit:: execute

   Groups various list of commands, that can be executed before specific phases. Currently this
   contains only ``pre_run`` phase, which is executed before any collection of the data. This is
   mainly meant to execute compiling of the binaries and other stuff to ease the development. Note
   that these commands are executed without shell, but any risks of commands executed by these
   commands fall entirely into the user hands and we have no responsibility for them.

   All of these list are as follows:

   .. code-block:: yaml

           execute:
             pre_run:
               - echo "Running the code again"
               - make
               - make install

   The list of commands above first outputs some text into the standard output, then it runs the
   makefile to compile the collected binary and then installs it.

.. confkey:: execute.pre_run

   ``[local-only]]`` Runs the code before the collection of the data. This is meant to prepare the
   binaries and other settings for the actual collection of the new data.

.. confunit:: cmds

    ``[local-only]`` Refer to :munit:`cmds`.

.. confunit:: args

    ``[local-only]`` Refer to :munit:`args`.

.. confunit:: workloads

    ``[local-only]`` Refer to :munit:`workloads`

.. confunit:: collectors

    ``[local-only]`` Refer to :munit:`collectors`

.. confunit:: postprocessors

    ``[local-only]`` Refer to :munit:`postprocessors`

.. confunit:: profiles

   Groups various option specific for profiles, such as strategies for adding or generating
   profiles

.. confkey:: profiles.register_after_run

   If the key is set to a true value (can be 1, true, True, yes, etc.), then after newly generated
   profile (e.g. by running ``perun run matrix``) is automatically registered in the appropriate
   minor version index.

.. confunit:: degradation

   Speficies the list of strategies and how they are applied when checked for degradation in
   methods.

.. confkey:: degradation.collect_before_check

    ``[recursive]`` If set to true, then before checking profiles of two minor versions, we run the
    collection for job matrix to collect fresh or unexisting profiles. By default, the output of
    this phase is discarded into a ``devnull``. This behaviour can be changed by setting the
    :ckey:`degradation.log_collect`.

.. confkey:: degradation.log_collect

    ``[recursive]`` If both :ckey:`degradation.log_collect` and
    :ckey:`degradation.collect_before_check` are set to true, then the precollect phase will be
    saved into a log of form ``%minor_version$-precollect.log``. Otherwise, the output will be
    stashed into a black hole (i.e. ``devnull``).

.. confkey:: degradation.apply

    ``[recursive]`` Specifies which strategies are picked for application, if more than one
    strategy satisfies the specified constraints. If the key is set to ``first``, then first
    strategy from the ordered list of :ckey:`degradation.strategies` is applied; otherwise if the
    key is set to ``all``, then all of the strategies from the ordered list are applied.

.. confkey:: degradation.strategies

    ``[gathered]`` Specifies the rules for application of the performance degradation methods for
    profiles with corresponding profile configurations (e.g. with concrete profile type, specified
    collector, etc.). Refer to :ref:`degradation-config` for more details about application of
    strategies.

    The following configuration will apply the :ref:`degradation-method-bmoe` method for all of the
    `mixed` types of the profiles, which were postprocessed using the
    :ref:`postprocessors-regression-analysis` and :ref:`degradation-method-aat` otherwise.

    .. code-block:: yaml

        degradation:
          strategies:
            - type: mixed
              postprocessor: regression_analysis
              method: bmoe
            - method: aat

.. confkey:: generators.workload

    ``[gathered]`` Specifies generators of the workload. Each workload has to be specified by its
    ``id`` and ``type``, which corresponds to the name of the generator (currently we support only
    Integer generator, that generates the range of values). Further you can specify rest of the
    params, where each workload generator has different parameters. The specification can be as
    follows:

    .. code-block:: yaml

        generators:
          workload:
            - id: gen1
              type: integer
              profile_for_each_workload: True
            - id: gen2
              type: integer
              min_range: 10
              max_range: 100
              step: 10

    This specifies two integer workload generators ``gen1`` and ``gen2``. The first uses the
    default range, while the latter specifies the range 10, 20, ..., 100. If
    ``profile_for_each_workload`` is set to true value (true, yes, etc.), then isolate profile will
    be generated for each collected workload. Otherwise the resulting profiles are merged into the
    one profile, and each resources has additional key called "workload", that allows using
    :ref:`postprocessors-regression-analysis` of amount depending on the workload.

    For more details about supported generators refer to :ref:`jobs-workload-generators`.

.. _config-templates:

Predefined Configuration Templates
----------------------------------

.. automodule:: perun.logic.config_templates

.. _config-cli:

Command Line Interface
----------------------

We advise to manipulate with configurations using the ``perun config --edit`` command. In order to
change the nearest local (resp. global) configuration run ``perun config --local --edit`` (resp.
``perun config --shared --edit``).

.. click:: perun.cli_groups.config_cli:config
   :prog: perun config

.. click:: perun.cli_groups.config_cli:config_get
   :prog: perun config get

.. click:: perun.cli_groups.config_cli:config_set
   :prog: perun config set

.. click:: perun.cli_groups.config_cli:config_edit
   :prog: perun config edit
