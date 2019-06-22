"""Perun can be run from the command line (if correctly installed) using the
command interface inspired by git.

The Command Line Interface is implemented using the Click_ library, which
allows both effective definition of new commands and finer parsing of the
command line arguments. The intefrace can be broken into several groups:

    1. **Core commands**: namely ``init``, ``config``, ``add``, ``rm``,
    ``status``, ``log``, ``run`` commands (which consists of commands ``run
    job`` and ``run matrix``) and ``check`` commands (which consists of
    commands ``check all``, ``check head`` and ``check profiles``).
    These commands automate the creation of performance profiles, detection
    of performance degradation and are used for management of the Perun
    repository. Refer to :ref:`cli-main-ref` for details about commands.

    2. **Collect commands**: group of ``collect COLLECTOR`` commands, where
    ``COLLECTOR`` stands for one of the collector of :ref:`collectors-list`.
    Each ``COLLECTOR`` has its own API, refer to :ref:`cli-collect-units-ref`
    for thorough description of API of individual collectors.

    3. **Postprocessby commands**: group of ``postprocessby POSTPROCESSOR``
    commands, where ``POSTPROCESSOR`` stands for one of the postprocessor of
    :ref:`postprocessors-list`. Each ``POSTPROCESSOR`` has its own API, refer
    to :ref:`cli-postprocess-units-ref` for thorough description of API of
    individual postprocessors.

    4. **View commands**: group of ``view VISUALIZATION`` commands, where
    ``VISUALIZATION`` stands for one of the visualizer of :ref:`views-list`.
    Each ``VISUALIZATION`` has its own API, refer to :ref:`cli-views-units-ref`
    for thorough description of API of individual views.

    5. **Utility commands**: group of commands used for developing Perun
    or for maintenance of the Perun instances. Currently this group contains
    ``create`` command for faster creation of new modules.

Graphical User Interface is currently in development and hopefully will extend
the flexibility of Perun's usage.

.. _Click: http://click.pocoo.org/5/
"""

import os
import pkgutil
import sys
import distutils.util as dutils
import termcolor

import click

import perun.collect
import perun.check.factory as check
import perun.fuzz.factory as fuzz
import perun.logic.commands as commands
import perun.logic.runner as runner
import perun.logic.pcs as pcs
import perun.logic.config as perun_config
import perun.postprocess
import perun.profile.factory as profiles
import perun.utils as utils
import perun.utils.script_helpers as scripts
import perun.utils.cli_helpers as cli_helpers
import perun.utils.log as perun_log
import perun.view
from perun.utils.exceptions import UnsupportedModuleException, UnsupportedModuleFunctionException, \
    NotPerunRepositoryException, IncorrectProfileFormatException, EntryNotFoundException, \
    MissingConfigSectionException, ExternalEditorErrorException

__author__ = 'Tomas Fiedor'


@click.group()
@click.option('--no-pager', default=False, is_flag=True,
              help='Disables the paging of the long standard output (currently'
              ' affects only ``status`` and ``log`` outputs). See '
              ':ckey:`paging` to change the default paging strategy.')
@click.option('--verbose', '-v', count=True, default=0,
              help='Increases the verbosity of the standard output. Verbosity '
              'is incremental, and each level increases the extent of output.')
@click.option('--version', help='Prints the current version of Perun.',
              is_eager=True, is_flag=True, default=False,
              callback=cli_helpers.print_version)
def cli(verbose=0, no_pager=False, **_):
    """Perun is an open source light-weight Performance Versioning System.

    In order to initialize Perun in current directory run the following::

        perun init

    This initializes basic structure in ``.perun`` directory, together with
    possible reinitialization of git repository in current directory. In order
    to set basic configuration and define jobs for your project run the
    following::

        perun config --edit

    This opens editor and allows you to specify configuration of your project
    and choose set of collectors for capturing resources. See :doc:`jobs` and
    :doc:`config` for more details.

    In order to generate first set of profiles for your current ``HEAD`` run the
    following::

        perun run matrix
    """
    # by default the pager is suppressed, and only calling it from the CLI enables it,
    # through --no-pager set by default to False you enable the paging
    perun_log.SUPPRESS_PAGING = no_pager

    # set the verbosity level of the log
    if perun_log.VERBOSITY < verbose:
        perun_log.VERBOSITY = verbose


@cli.group()
@click.option('--local', '-l', 'store_type', flag_value='local',
              help='Sets the local config, i.e. ``.perun/local.yml``, as the source config.')
@click.option('--shared', '-h', 'store_type', flag_value='shared',
              help='Sets the shared config, i.e. ``shared.yml.``, as the source config')
@click.option('--nearest', '-n', 'store_type', flag_value='recursive', default=True,
              help='Sets the nearest suitable config as the source config. The'
              ' lookup strategy can differ for ``set`` and '
              '``get``/``edit``.')
@click.pass_context
def config(ctx, **kwargs):
    """Manages the stored local and shared configuration.

    Perun supports two external configurations:

        1. ``local.yml``: the local configuration stored in ``.perun``
           directory, containing the keys such as specification of wrapped
           repository or job matrix used for quick generation of profiles (run
           ``perun run matrix --help`` or refer to :doc:`jobs` for information
           how to construct the job matrix).

        2. ``shared.yml``:  the global configuration shared by all perun
           instances, containing shared keys, such as text editor, formatting
           string, etc.

    The syntax of the ``<key>`` in most operations consists of section
    separated by dots, e.g. ``vcs.type`` specifies ``type`` key in ``vcs``
    section. The lookup of the ``<key>`` can be performed in three modes,
    ``--local``, ``--shared`` and ``--nearest``, locating or setting the
    ``<key>`` in local, shared or nearest configuration respectively (e.g. when
    one is trying to get some key, there may be nested perun instances that do
    not contain the given key). By default, perun operates in the nearest
    config mode.

    Refer to :doc:`config` for full description of configurations and
    :ref:`config-types` for full list of configuration options.

    E.g. using the following one can retrieve the type of the nearest perun
    instance wrapper:

    .. code-block:: bash

        $ perun config get vcs.type
        vcs.type: git
    """
    ctx.obj = kwargs


@config.command('get')
@click.argument('key', required=True, metavar='<key>',
                callback=cli_helpers.config_key_validation_callback)
@click.pass_context
def config_get(ctx, key):
    """Looks up the given ``<key>`` within the configuration hierarchy and returns
    the stored value.

    The syntax of the ``<key>`` consists of section separated by dots, e.g.
    ``vcs.type`` specifies ``type`` key in ``vcs`` section. The lookup of the
    ``<key>`` can be performed in three modes, ``--local``, ``--shared`` and
    ``--nearest``, locating the ``<key>`` in local, shared or nearest
    configuration respectively (e.g. when one is trying to get some key, there
    may be nested perun instances that do not contain the given key). By
    default, perun operates in the nearest config mode.

    Refer to :doc:`config` for full description of configurations and
    :ref:`config-types` for full list of configuration options.

    E.g. using the following can retrieve the type of the nearest perun
    wrapper:

    .. code-block:: bash

        $ perun config get vcs.type
        vcs.type: git

        $ perun config --shared get general.editor
        general.editor: vim
    """
    try:
        commands.config_get(ctx.obj['store_type'], key)
    except MissingConfigSectionException as mcs_err:
        perun_log.error("error while getting key '{}': {}".format(
            key, str(mcs_err))
        )


@config.command('set')
@click.argument('key', required=True, metavar='<key>',
                callback=cli_helpers.config_key_validation_callback)
@click.argument('value', required=True, metavar='<value>')
@click.pass_context
def config_set(ctx, key, value):
    """Sets the value of the ``<key>`` to the given ``<value>`` in the target
    configuration file.

    The syntax of the ``<key>`` corresponds of section separated by dots, e.g.
    ``vcs.type`` specifies ``type`` key in ``vcs`` section. Perun sets the
    ``<key>`` in three modes, ``--local``, ``--shared`` and ``--nearest``,
    which sets the ``<key>`` in local, shared or nearest configuration
    respectively (e.g.  when one is trying to get some key, there may be nested
    perun instances that do not contain the given key). By default, perun will
    operate in the nearest config mode.

    The ``<value>`` is arbitrary depending on the key.

    Refer to :doc:`config` for full description of configurations and
    :ref:`config-types` for full list of configuration options and their
    values.

    E.g. using the following can set the log format for nearest perun instance
    wrapper:

    .. code-block:: bash

        $ perun config set format.shortlog "| %source% | %collector% |"
        format.shortlog: | %source% | %collector% |
    """
    commands.config_set(ctx.obj['store_type'], key, value)


@config.command('edit')
@click.pass_context
def config_edit(ctx):
    """Edits the configuration file in the external editor.

    The used editor is specified by the :ckey:`general.editor` option,
    specified in the nearest perun configuration..

    Refer to :doc:`config` for full description of configurations and
    :ref:`config-types` for full list of configuration options.
    """
    try:
        commands.config_edit(ctx.obj['store_type'])
    except (ExternalEditorErrorException, MissingConfigSectionException) as editor_exception:
        perun_log.error("could not invoke external editor: {}".format(
            str(editor_exception)))


@config.command('reset')
@click.argument('config_template', required=False, default='master',
                metavar='<template>')
@click.pass_context
def config_reset(ctx, config_template):
    """Resets the configuration file to a sane default.

    If we are resetting the local configuration file we can specify a <template> that
    will be used to generate a predefined set of options. Currently we support the following:

      1. **user** configuration is meant for beginner users, that have no experience with Perun and
      have not read the documentation thoroughly. This contains a basic preconfiguration that should
      be applicable for most of the projects---data are collected by :ref:`collectors-time` and are
      automatically registered in the Perun after successful run. The performance is checked using
      the :ref:`degradation-method-aat`. Missing profiling info will be looked up automatically.

      2. **developer** configuration is meant for advanced users, that have some understanding of
      profiling and/or Perun. Fair amount of options are up to the user, such as the collection of
      the data and the commands that will be profiled.

      3. **master** configuration is meant for experienced users. The configuration will be mostly
      empty.

    See :ref:`config-templates` to learn more about predefined configuration options.
    """
    try:
        commands.config_reset(ctx.obj['store_type'], config_template)
    except NotPerunRepositoryException as npre:
        perun_log.error("could not reset the {} configuration: {}".format(
            ctx.obj['store_type'], str(npre)
        ))


def configure_local_perun(perun_path):
    """Configures the local perun repository with the interactive help of the user

    :param str perun_path: destination path of the perun repository
    :raises: ExternalEditorErrorException: when underlying editor makes any mistake
    """
    editor = perun_config.lookup_key_recursively('general.editor')
    local_config_file = os.path.join(perun_path, '.perun', 'local.yml')
    utils.run_external_command([editor, local_config_file])


@cli.command()
@click.argument('dst', required=False, default=os.getcwd(), metavar='<path>')
@click.option('--vcs-type', metavar='<type>', default='git',
              type=click.Choice(utils.get_supported_module_names('vcs')),
              help="In parallel to initialization of Perun, initialize the vcs"
              " of <type> as well (by default ``git``).")
@click.option('--vcs-path', metavar='<path>',
              help="Sets the destination of wrapped vcs initialization at "
              "<path>.")
@click.option('--vcs-param', nargs=2, metavar='<param>', multiple=True,
              callback=cli_helpers.vcs_parameter_callback,
              help="Passes additional (key, value) parameter to initialization"
              " of version control system, e.g. ``separate-git-dir dir``.")
@click.option('--vcs-flag', nargs=1, metavar='<flag>', multiple=True,
              callback=cli_helpers.vcs_parameter_callback,
              help="Passes additional flag to a initialization of version "
              "control system, e.g. ``bare``.")
@click.option('--configure', '-c', is_flag=True, default=False,
              help='After successful initialization of both systems, opens '
              'the local configuration using the :ckey:`editor` set in shared '
              'config.')
@click.option('--config-template', '-t', type=click.STRING, default='master',
              help='States the configuration template that will be used for initialization of local'
                   ' configuration. See :ref:`config-templates` for more details about predefined '
                   ' configurations.')
def init(dst, configure, config_template, **kwargs):
    """Initializes performance versioning system at the destination path.

    ``perun init`` command initializes the perun's infrastructure with basic
    file and directory structure inside the ``.perun`` directory. Refer to
    :ref:`internals-overview` for more details about storage of Perun. By
    default following directories are created:

        1. ``.perun/jobs``: storage of performance profiles not yet assigned to
           concrete minor versions.

        2. ``.perun/objects``: storage of packed contents of performance
           profiles and additional informations about minor version of wrapped
           vcs system.

        3. ``.perun/cache``: fast access cache of selected latest unpacked
           profiles

        4. ``.perun/local.yml``: local configuration, storing specification of
           wrapped repository, jobs configuration, etc. Refer to :doc:`config`
           for more details.

    The infrastructure is initialized at <path>. If no <path> is given, then
    current working directory is used instead. In case there already exists a
    performance versioning system, the infrastructure is only reinitialized.

    By default, a control system is initialized as well. This can be changed by
    by setting the ``--vcs-type`` parameter (currently we support ``git`` and
    ``tagit``---a lightweight git-based wrapped based on tags). Additional
    parameters can be passed to the wrapped control system initialization using
    the ``--vcs-params``.
    """
    try:
        commands.init(dst, config_template, **kwargs)

        if configure:
            # Run the interactive configuration of the local perun repository (populating .yml)
            configure_local_perun(dst)
        else:
            msg = "\nIn order to automatically run jobs configure the matrix at:\n"
            msg += "\n" + (" "*4) + ".perun/local.yml\n"
            perun_log.quiet_info(msg)
    except (UnsupportedModuleException, UnsupportedModuleFunctionException) as unsup_module_exp:
        perun_log.error("error while initializing perun: {}".format(str(unsup_module_exp)))
    except PermissionError:
        perun_log.error(
            "writing to shared config 'shared.yml' requires root permissions")
    except (ExternalEditorErrorException, MissingConfigSectionException):
        err_msg = "cannot launch default editor for configuration.\n"
        err_msg += "Please set 'general.editor' key to a valid text editor (e.g. vim)."
        perun_log.error(err_msg)


@cli.command()
@click.argument('profile', required=True, metavar='<profile>', nargs=-1,
                callback=cli_helpers.lookup_added_profile_callback)
@click.option('--minor', '-m', required=False, default=None, metavar='<hash>', is_eager=True,
              callback=cli_helpers.lookup_minor_version_callback,
              help='<profile> will be stored at this minor version (default is HEAD).')
@click.option('--keep-profile', is_flag=True, required=False, default=False,
              help='Keeps the profile in filesystem after registering it in'
              ' Perun storage. Otherwise it is deleted.')
@click.option('--force', '-f', is_flag=True, default=False, required=False,
              help='If set to true, then the profile will be registered in the <hash> minor version'
                   'index, even if its origin <hash> is different. WARNING: This can screw the '
                   'performance history of your project.')
def add(profile, minor, **kwargs):
    """Links profile to concrete minor version storing its content in the
    ``.perun`` dir and registering the profile in internal minor version index.

    In order to link <profile> to given minor version <hash> the following
    steps are executed:

        1. We check in <profile> that its :preg:`origin` key corresponds to
           <hash>. This serves as a check, that we do not assign profiles to
           different minor versions.

        2. The :preg:`origin` is removed and contents of <profile> are
           compresed using `zlib` compression method.

        3. Binary header for the profile is constructed.

        4. Compressed contents are appended to header, and this blob is stored
           in ``.perun/objects`` directory.

        5. New blob is registered in <hash> minor version's index.

        6. Unless ``--keep-profile`` is set. The original profile is deleted.

    If no `<hash>` is specified, then current ``HEAD`` of the wrapped version
    control system is used instead. Massaging of <hash> is taken care of by
    underlying version control system (e.g. git uses ``git rev-parse``).

    <profile> can either be a ``pending tag``, ``pending tag range`` or a
    fullpath. ``Pending tags`` are in form of ``i@p``, where ``i`` stands
    for an index in the pending profile directory (i.e. ``.perun/jobs``)
    and ``@p`` is literal suffix.  The ``pending tag range`` is in form
    of ``i@p-j@p``, where both ``i`` and ``j`` stands for indexes in the
    pending profiles. The ``pending tag range`` then represents all of
    the profiles in the interval <i, j>. When ``i > j``, then no profiles
    will be add; when ``j``; when ``j`` is bigger than the number of
    pending profiles, then all of the non-existing pending profiles will
    be obviously skipped.
    Run ``perun status`` to see the `tag` anotation of pending profiles.
    Tags consider the sorted order as specified by the following option
    :ckey:`format.sort_profiles_by`.

    Example of adding profiles:

    .. code-block:: bash

        $ perun add mybin-memory-input.txt-2017-03-01-16-11-04.perf

    This command adds the profile collected by `memory` collector during
    profiling ``mybin`` command with ``input.txt`` workload on 1st March at
    16:11 to the current ``HEAD``.

    An error is raised if the command is executed outside of range of any
    perun, if <profile> points to incorrect profile (i.e. not w.r.t.
    :ref:`profile-spec`) or <hash> does not point to valid minor version ref.

    See :doc:`internals` for information how perun handles profiles internally.
    """
    try:
        warning_message = 'Warning: Are you sure you want to force the add?' \
                          'This will make the performance history of your project imprecise ' \
                          'or simply wrong.'
        if not kwargs['force'] or click.confirm(warning_message):
            commands.add(profile, minor, **kwargs)
    except (NotPerunRepositoryException, IncorrectProfileFormatException) as exception:
        perun_log.error("error while adding profile:{}".format(str(exception)))


@cli.command('rm')
@click.argument('profile', required=True, metavar='<profile>', nargs=-1,
                callback=cli_helpers.lookup_removed_profile_callback)
@click.option('--minor', '-m', required=False, default=None, metavar='<hash>', is_eager=True,
              callback=cli_helpers.lookup_minor_version_callback,
              help='<profile> will be stored at this minor version (default is HEAD).')
@click.option('--remove-all', '-A', is_flag=True, default=False,
              help="Removes all occurrences of <profile> from the <hash> index.")
def remove(profile, minor, **kwargs):
    """Unlinks the profile from the given minor version, keeping the contents
    stored in ``.perun`` directory.

    <profile> is unlinked in the following steps:

        1. <profile> is looked up in the <hash> minor version's internal index.

        2. In case <profile> is not found. An error is raised.

        3. Otherwise, the record corresponding to <hash> is erased. However,
           the original blob is kept in ``.perun/objects``.

    If no `<hash>` is specified, then current ``HEAD`` of the wrapped version
    control system is used instead. Massaging of <hash> is taken care of by
    underlying version control system (e.g. git uses ``git rev-parse``).

    <profile> can either be a ``index tag`` or a path specifying the profile.
    ``Index tags`` are in form of ``i@i``, where ``i`` stands for an index in
    the minor version's index and ``@i`` is literal suffix. Run ``perun
    status`` to see the `tags` of current ``HEAD``'s index. The
    ``index tag range`` is in form of ``i@i-j@i``, where both ``i`` and ``j``
    stands for indexes in the minor version's index. The ``index tag range``
    then represents all of the profiles in the interval <i, j>. registered
    in index. When ``i > j``, then no profiles will be removed; when ``j``;
    when ``j`` is bigger than the number of pending profiles, then all of
    the non-existing pending profiles will be obviously skipped.
    Tags consider the sorted order as specified by the following option
    :ckey:`format.sort_profiles_by`.

    Examples of removing profiles:

    .. code-block:: bash

        $ perun rm 2@i

    This commands removes the third (we index from zero) profile in the index
    of registered profiles of current ``HEAD``.

    An error is raised if the command is executed outside of range of any
    Perun or if <profile> is not found inside the <hash> index.

    See :doc:`internals` for information how perun handles profiles internally.
    """
    try:
        commands.remove(profile, minor, **kwargs)
    except (NotPerunRepositoryException, EntryNotFoundException) as exception:
        perun_log.error("could not remove profiles: {}".format(str(exception)))


@cli.command()
@click.argument('head', required=False, default=None, metavar='<hash>')
@click.option('--short', '-s', is_flag=True, default=False,
              help="Shortens the output of ``log`` to include only most "
              "necessary information.")
def log(head, **kwargs):
    """Shows history of versions and associated profiles.

    Shows the history of the wrapped version control system and all of the
    associated profiles starting from the <hash> point, outputing the
    information about number of profiles, about descriptions ofconcrete minor
    versions, their parents, parents etc.

    If ``perun log --short`` is issued, the shorter version of the ``log`` is
    outputted.

    In no <hash> is given, then HEAD of the version control system is used as a starting point.

    Unless ``perun --no-pager log`` is issued as command, or appropriate
    :ckey:`paging` option is set, the outputs of log will be paged (by
    default using ``less``.

    Refer to :ref:`logs-log` for information how to customize the outputs of
    ``log`` or how to set :ckey:`format.shortlog` in nearest
    configuration.
    """
    try:
        commands.log(head, **kwargs)
    except (NotPerunRepositoryException, UnsupportedModuleException) as exception:
        perun_log.error("could not print the repository history: {}".format(str(exception)))


@cli.command()
@click.option('--short', '-s', required=False, default=False, is_flag=True,
              help="Shortens the output of ``status`` to include only most"
              " necessary information.")
@click.option('--sort-by', '-sb', 'format__sort_profiles_by', nargs=1,
              type=click.Choice(profiles.ProfileInfo.valid_attributes),
              callback=cli_helpers.set_config_option_from_flag(
                  pcs.local_config, 'format.sort_profiles_by', str
              ),
              help="Sets the <key> in the local configuration for sorting profiles. "
                   "Note that after setting the <key> it will be used for sorting which is "
                   "considered in pending and index tags!")
def status(**kwargs):
    """Shows the status of vcs, associated profiles and perun.

    Shows the status of both the nearest perun and wrapped version control
    system. For vcs this outputs e.g. the current minor version ``HEAD``,
    current major version and description of the ``HEAD``.  Moreover ``status``
    prints the lists of tracked and pending (found in ``.perun/jobs``) profiles
    lexicographically sorted along with additional information such as their
    types and creation times.

    Unless ``perun --no-pager status`` is issued as command, or appropriate
    :ckey:`paging` option is set, the outputs of status will be paged (by
    default using ``less``.

    An error is raised if the command is executed outside of range of any
    perun, or configuration misses certain configuration keys
    (namely ``format.status``).

    Profiles (both registered in index and stored in pending directory) are sorted
    according to the :ckey:`format.sort_profiles_by`. The option ``--sort-by``
    sets this key in the local configuration for further usage. This means that
    using the pending or index tags will consider this order.

    Refer to :ref:`logs-status` for information how to customize the outputs of
    ``status`` or how to set :ckey:`format.status` in nearest
    configuration.
    """
    try:
        commands.status(**kwargs)
    except (NotPerunRepositoryException, UnsupportedModuleException,
            MissingConfigSectionException) as exception:
        perun_log.error("could not print status of repository: {}".format(str(exception)))


@cli.group()
@click.argument('profile', required=True, metavar='<profile>',
                callback=cli_helpers.lookup_any_profile_callback)
@click.option('--minor', '-m', nargs=1, default=None, is_eager=True,
              callback=cli_helpers.lookup_minor_version_callback,
              help='Will check the index of different minor version <hash>'
              ' during the profile lookup')
@click.pass_context
def show(ctx, profile, **_):
    """Interprets the given profile using the selected visualization technique.

    Looks up the given profile and interprets it using the selected
    visualization technique. Some of the techniques outputs either to
    terminal (using ``ncurses``) or generates HTML files, which can be
    browseable in the web browser (using ``bokeh`` library). Refer to concrete
    techniques for concrete options and limitations.

    The shown <profile> will be looked up in the following steps:

        1. If <profile> is in form ``i@i`` (i.e, an `index tag`), then `ith`
           record registered in the minor version <hash> index will be shown.

        2. If <profile> is in form ``i@p`` (i.e., an `pending tag`), then
           `ith` profile stored in ``.perun/jobs`` will be shown.

        3. <profile> is looked-up within the minor version <hash> index for a
           match. In case the <profile> is registered there, it will be shown.

        4. <profile> is looked-up within the ``.perun/jobs`` directory. In case
           there is a match, the found profile will be shown.

        5. Otherwise, the directory is walked for any match. Each found match
           is asked for confirmation by user.

    Tags consider the sorted order as specified by the following option
    :ckey:`format.sort_profiles_by`.

    Example 1. The following command will show the first profile registered at
    index of ``HEAD~1`` commit. The resulting graph will contain bars
    representing sum of amounts per each subtype of resources and will be shown
    in the browser::

        perun show -m HEAD~1 0@i bars sum --of 'amount' --per 'subtype' -v

    Example 2. The following command will show the profile at the absolute path
    using in raw JSON format::

        perun show ./echo-time-hello-2017-04-02-13-13-34-12.perf raw

    For a thorough list and description of supported visualization techniques
    refer to :ref:`views-list`.
    """
    ctx.obj = profile


@cli.group()
@click.argument('profile', required=True, metavar='<profile>',
                callback=cli_helpers.lookup_any_profile_callback)
@click.option('--output-filename-template', '-ot', default=None,
              callback=cli_helpers.set_config_option_from_flag(
                  perun_config.runtime, 'format.output_profile_template', str
              ), help='Specifies the template for automatic generation of output filename'
              ' This way the postprocessed file will have a resulting filename w.r.t to this'
              ' parameter. Refer to :ckey:`format.output_profile_template` for more'
              ' details about the format of the template.')
@click.option('--minor', '-m', nargs=1, default=None, is_eager=True,
              callback=cli_helpers.lookup_minor_version_callback,
              help='Will check the index of different minor version <hash>'
              ' during the profile lookup')
@click.pass_context
def postprocessby(ctx, profile, **_):
    """Postprocesses the given stored or pending profile using selected
    postprocessor.

    Runs the single postprocessor unit on given looked-up profile. The
    postprocessed file will be then stored in ``.perun/jobs/`` directory as a
    file, by default with filanem in form of::

        bin-collector-workload-timestamp.perf

    The postprocessed <profile> will be looked up in the following steps:

        1. If <profile> is in form ``i@i`` (i.e, an `index tag`), then `ith`
           record registered in the minor version <hash> index will be
           postprocessed.

        2. If <profile> is in form ``i@p`` (i.e., an `pending tag`), then
           `ith` profile stored in ``.perun/jobs`` will be postprocessed.

        3. <profile> is looked-up within the minor version <hash> index for a
           match. In case the <profile> is registered there, it will be
           postprocessed.

        4. <profile> is looked-up within the ``.perun/jobs`` directory. In case
           there is a match, the found profile will be postprocessed.

        5. Otherwise, the directory is walked for any match. Each found match
           is asked for confirmation by user.

    Tags consider the sorted order as specified by the following option
    :ckey:`format.sort_profiles_by`.

    For checking the associated `tags` to profiles run ``perun status``.

    Example 1. The following command will postprocess the given profile
    stored at given path by normalizer, i.e. for each snapshot, the resources
    will be normalized to the interval <0, 1>::

        perun postprocessby ./echo-time-hello-2017-04-02-13-13-34-12.perf normalizer

    Example 2. The following command will postprocess the second profile stored
    in index of commit preceeding the current head using interval regression
    analysis::

        perun postprocessby -m HEAD~1 1@i regression_analysis --method=interval

    For a thorough list and description of supported postprocessors refer to
    :ref:`postprocessors-list`. For a more subtle running of profiling jobs and
    more complex configuration consult either ``perun run matrix --help`` or
    ``perun run job --help``.
    """
    ctx.obj = profile


@cli.group()
@click.option('--minor-version', '-m', 'minor_version_list', nargs=1, multiple=True,
              callback=cli_helpers.minor_version_list_callback, default=[
                  'HEAD'],
              help='Specifies the head minor version, for which the profiles will be collected.')
@click.option('--crawl-parents', '-cp', is_flag=True, default=False, is_eager=True,
              help='If set to true, then for each specified minor versions, profiles for parents'
                   ' will be collected as well')
@click.option('--cmd', '-c', nargs=1, required=False, multiple=True, default=[''],
              help='Command that is being profiled. Either corresponds to some'
              ' script, binary or command, e.g. ``./mybin`` or ``perun``.')
@click.option('--args', '-a', nargs=1, required=False, multiple=True,
              help='Additional parameters for <cmd>. E.g. ``status`` or '
              '``-al`` is command parameter.')
@click.option('--workload', '-w', nargs=1, required=False, multiple=True, default=[''],
              help='Inputs for <cmd>. E.g. ``./subdir`` is possible workload'
              'for ``ls`` command.')
@click.option('--params', '-p', nargs=1, required=False, multiple=True,
              callback=cli_helpers.single_yaml_param_callback,
              help='Additional parameters for called collector read from '
              'file in YAML format.')
@click.option('--output-filename-template', '-ot', default=None,
              callback=cli_helpers.set_config_option_from_flag(
                  perun_config.runtime, 'format.output_profile_template', str
              ), help='Specifies the template for automatic generation of output filename'
              ' This way the file with collected data will have a resulting filename w.r.t '
              ' to this parameter. Refer to :ckey:`format.output_profile_template` for more'
              ' details about the format of the template.')
@click.pass_context
def collect(ctx, **kwargs):
    """Generates performance profile using selected collector.

    Runs the single collector unit (registered in Perun) on given profiled
    command (optionaly with given arguments and workloads) and generates
    performance profile. The generated profile is then stored in
    ``.perun/jobs/`` directory as a file, by default with filename in form of::

        bin-collector-workload-timestamp.perf

    Generated profiles will not be postprocessed in any way. Consult ``perun
    postprocessby --help`` in order to postprocess the resulting profile.

    The configuration of collector can be specified in external YAML file given
    by the ``-p``/``--params`` argument.

    For a thorough list and description of supported collectors refer to
    :ref:`collectors-list`. For a more subtle running of profiling jobs and
    more complex configuration consult either ``perun run matrix --help`` or
    ``perun run job --help``.
    """
    ctx.obj = kwargs


@cli.group()
@click.option('--output-filename-template', '-ot', default=None,
              callback=cli_helpers.set_config_option_from_flag(
                  perun_config.runtime, 'format.output_profile_template', str
              ), help='Specifies the template for automatic generation of output filename'
              ' This way the file with collected data will have a resulting filename w.r.t '
              ' to this parameter. Refer to :ckey:`format.output_profile_template` for more'
              ' details about the format of the template.')
@click.option('--minor-version', '-m', 'minor_version_list', nargs=1, multiple=True,
              callback=cli_helpers.minor_version_list_callback, default=[
                  'HEAD'],
              help='Specifies the head minor version, for which the profiles will be collected.')
@click.option('--crawl-parents', '-c', is_flag=True, default=False, is_eager=True,
              help='If set to true, then for each specified minor versions, profiles for parents'
                   ' will be collected as well')
@click.option('--force-dirty', '-f', is_flag=True, default=False,
              callback=cli_helpers.unsupported_option_callback,
              help='If set to true, then even if the repository is dirty, '
                   'the changes will not be stashed')
@click.pass_context
def run(ctx, **kwargs):
    """Generates batch of profiles w.r.t. specification of list of jobs.

    Either runs the job matrix stored in local.yml configuration or lets the
    user construct the job run using the set of parameters.
    """
    ctx.obj = kwargs


@run.command()
@click.pass_context
@click.option('--without-vcs-history', '-q', 'quiet', is_flag=True, default=False,
              help="Will not print the VCS history tree during the collection of the data.")
def matrix(ctx, quiet, **kwargs):
    """Runs the jobs matrix specified in the local.yml configuration.

    This commands loads the jobs configuration from local configuration, builds
    the `job matrix` and subsequently runs the jobs collecting list of
    profiles. Each profile is then stored in ``.perun/jobs`` directory and
    moreover is annotated using by setting :preg:`origin` key to current
    ``HEAD``. This serves as check to not assing such profiles to different
    minor versions.

    The job matrix is defined in the yaml format and consists of specification
    of binaries with corresponding arguments, workloads, supported collectors
    of profiling data and postprocessors that alter the collected profiles.

    Refer to :doc:`jobs` and :ref:`jobs-matrix` for more details how to specify
    the job matrix inside local configuration and to :doc:`config` how to work
    with Perun's configuration files.
    """
    kwargs.update({'minor_version_list': ctx.obj['minor_version_list']})
    kwargs.update({'with_history': not quiet})
    if runner.run_matrix_job(**kwargs) != runner.CollectStatus.OK:
        perun_log.error("job specification failed in one of the phases")


@run.command()
@click.option('--cmd', '-b', nargs=1, required=True, multiple=True,
              help='Command that is being profiled. Either corresponds to some'
              ' script, binary or command, e.g. ``./mybin`` or ``perun``.')
@click.option('--args', '-a', nargs=1, required=False, multiple=True,
              help='Additional parameters for <cmd>. E.g. ``status`` or '
              '``-al`` is command parameter.')
@click.option('--workload', '-w', nargs=1, required=False, multiple=True, default=[''],
              help='Inputs for <cmd>. E.g. ``./subdir`` is possible workload'
              'for ``ls`` command.')
@click.option('--collector', '-c', nargs=1, required=True, multiple=True,
              type=click.Choice(utils.get_supported_module_names('collect')),
              help='Profiler used for collection of profiling data for the'
              ' given <cmd>')
@click.option('--collector-params', '-cp', nargs=2, required=False, multiple=True,
              callback=cli_helpers.yaml_param_callback,
              help='Additional parameters for the <collector> read from the'
              ' file in YAML format')
@click.option('--postprocessor', '-p', nargs=1, required=False, multiple=True,
              type=click.Choice(
                  utils.get_supported_module_names('postprocess')),
              help='After each collection of data will run <postprocessor> to '
              'postprocess the collected resources.')
@click.option('--postprocessor-params', '-pp', nargs=2, required=False, multiple=True,
              callback=cli_helpers.yaml_param_callback,
              help='Additional parameters for the <postprocessor> read from the'
              ' file in YAML format')
@click.pass_context
def job(ctx, **kwargs):
    """Run specified batch of perun jobs to generate profiles.

    This command correspond to running one isolated batch of profiling jobs,
    outside of regular profilings. Run ``perun run matrix``, after specifying
    job matrix in local configuration to automate regular profilings of your
    project. After the batch is generated, each profile is taged with
    :preg:`origin` set to current ``HEAD``. This serves as check to not assing
    such profiles to different minor versions.

    By default the profiles computed by this batch job are stored inside the
    ``.perun/jobs/`` directory as a files in form of::

        bin-collector-workload-timestamp.perf

    In order to store generated profiles run the following, with ``i@p``
    corresponding to `pending tag`, which can be obtained by running ``perun
    status``::

        perun add i@p

    .. code-block:: bash

        perun run job -c time -b ./mybin -w file.in -w file2.in -p normalizer

    This command profiles two commands ``./mybin file.in`` and ``./mybin
    file2.in`` and collects the profiling data using the
    :ref:`collectors-time`. The profiles are afterwards normalized with the
    :ref:`postprocessors-normalizer`.

    .. code-block:: bash

        perun run job -c complexity -b ./mybin -w sll.cpp -cp complexity targetdir=./src

    This commands runs one job './mybin sll.cpp' using the
    :ref:`collectors-trace`, which uses custom binaries targeted at
    ``./src`` directory.

    .. code-block:: bash

        perun run job -c mcollect -b ./mybin -b ./otherbin -w input.txt -p normalizer -p clusterizer

    This commands runs two jobs ``./mybin input.txt`` and ``./otherbin
    input.txt`` and collects the profiles using the :ref:`collectors-memory`.
    The profiles are afterwards postprocessed, first using the
    :ref:`postprocessors-normalizer` and then with
    :ref:`postprocessors-regression-analysis`.

    Refer to :doc:`jobs` and :doc:`profile` for more details about automation
    and lifetimes of profiles. For list of available collectors and
    postprocessors refer to :ref:`collectors-list` and
    :ref:`postprocessors-list` respectively.
    """
    kwargs.update({'minor_version_list': ctx.obj['minor_version_list']})
    kwargs.update({'with_history': True})
    if runner.run_single_job(**kwargs) != runner.CollectStatus.OK:
        perun_log.error("job specification failed in one of the phases")


@cli.command('fuzz')
@click.option('--cmd', '-b', nargs=1, required=True,
              help='The command which will be fuzzed.')
@click.option('--args', '-a', nargs=1, required=False, default='',
              help='Arguments for the fuzzed command.')
@click.option('--initial-workload', '-w', nargs=1, required=True, multiple=True,
              help='Initial sample of workloads, that will be source of the fuzzing.')
@click.option('--collector', '-c', nargs=1, default='time',
              type=click.Choice(utils.get_supported_module_names('collect')),
              help='Collector that will be used to collect performance data.')
@click.option('--collector-params', '-cp', nargs=2, required=False, multiple=True,
              callback=cli_helpers.yaml_param_callback,
              help='Additional parameters for the <collector> read from the'
                   ' file in YAML format')
@click.option('--postprocessor', '-p', nargs=1, required=False, multiple=True,
              type=click.Choice(
                  utils.get_supported_module_names('postprocess')),
              help='After each collection of data will run <postprocessor> to '
                   'postprocess the collected resources.')
@click.option('--postprocessor-params', '-pp', nargs=2, required=False, multiple=True,
              callback=cli_helpers.yaml_param_callback,
              help='Additional parameters for the <postprocessor> read from the'
                   ' file in YAML format')
@click.option('--minor-version', '-m', 'minor_version_list', nargs=1,
              callback=cli_helpers.minor_version_list_callback, default=[
                  'HEAD'],
              help='Specifies the head minor version, for which the fuzzing will be performed.')
@click.option('--workloads-filter', '-wf', nargs=1, required=False,
              type=str, metavar='<regexp>', default="",
              help='Regular expression for filtering the workloads.')
@click.option('--source-path', '-s', nargs=1, required=False,
              type=click.Path(exists=True, readable=True), metavar='<path>',
              help='The path to the directory of the project source files.')
@click.option('--gcno-path', '-g', nargs=1, required=False,
              type=click.Path(exists=True, writable=True), metavar='<path>',
              help='The path to the directory where .gcno files are stored.')
@click.option('--output-dir', '-o', nargs=1, required=True,
              type=click.Path(exists=True, writable=True), metavar='<path>',
              help='The path to the directory where generated outputs will be stored.')
@click.option('--timeout', '-t', nargs=1, required=False, default=1800,
              type=click.IntRange(1, None, False), metavar='<int>',
              help='Time limit for fuzzing (in seconds).  Default value is 1800s.')
@click.option('--hang-timeout', '-h', nargs=1, required=False, default=10,
              type=click.IntRange(1, None, False), metavar='<int>',
              help='The time limit before input is classified as a hang (in seconds).'
              ' Default value is 30s.')
@click.option('--max', '-N', nargs=1, required=False,
              type=click.IntRange(1, None, False), metavar='<int>',
              help='The maximum size limit of the generated input file.'
              ' Value should be larger than any of the initial workload,'
              ' otherwise it will be adjusted, see \033[1m-a\033[0m resp. \033[1m-p\033[0m')
@click.option('--max-size-adjunct', '-ma', nargs=1, required=False,default=1000000,
              type=click.IntRange(0, None, False), metavar='<int>', 
              help='Max size expressed by adjunct. Using this option, max size of generated input'
              ' file will be set to (size of the largest workload + value).' 
              'Default value is 1 000 000 B = 1MB.')
@click.option('--max-size-percentual', '-mp', nargs=1, required=False,
              type=click.FloatRange(0.1, None, False), metavar='<float>',
              help='Max size expressed by percentage. Using this option, max size of generated' 
              ' input file will be set to (size of the largest workload * value).'
              ' E.g. 1.5, max_size=largest_workload_size * 1.5')
@click.option('--execs', '-e', nargs=1, required=False, default=100,
              type=click.IntRange(1, None, False), metavar='<int>',
              help='Defines maximum number executions while gathering interesiting inputs.')
@click.option('--interesting-files-limit', '-l', nargs=1, required=False,
              type=click.IntRange(1, None, False), metavar='<int>', default=20,
              help='Defines minimum number of gathered interesting inputs before perun testing.')
@click.option('--icovr', '-cr', nargs=1, required=False, default=1.5,
              type=click.FloatRange(0, None, False), metavar='<int>',
              help='Represents threshold of coverage increase against base coverage.'
              '  E.g 1.5, base coverage = 100 000, so threshold = 150 000.')
@click.option('--mut-count-strategy', '-mcs', nargs=1, required=False, default='mixed',
              type=click.Choice(['unitary', 'proportional', 'probabilistic', 'mixed']), metavar='<str>',
              help='Strategy which determines how many mutations will be generated by ceratain'
              ' fuzzing rule in one iteration: unitary|proportional|probabilistic|mixed')     
@click.option('--regex-rules', '-r', nargs=1, required=False, multiple=True,
              callback=cli_helpers.single_yaml_param_callback, metavar='<file>',
              help='Option for adding custom rules specified by regular expressions,'
              ' written in YAML format file.')
def fuzz_cmd(**kwargs):
    """Performs fuzzing for the specified command according to the initial sample of workload."""
    fuzz.run_fuzzing_for_command(**kwargs)


@cli.group('check')
@click.option('--compute-missing', '-c',
              callback=cli_helpers.set_config_option_from_flag(
                  perun_config.runtime, 'degradation.collect_before_check'),
              is_flag=True, default=False,
              help='whenever there are missing profiles in the given point of history'
              ' the matrix will be rerun and new generated profiles assigned.')
def check_group(**_):
    """Applies for the points of version history checks for possible performance changes.

    This command group either runs the checks for one point of history (``perun check head``) or for
    the whole history (``perun check all``). For each minor version (called the `target`) we iterate
    over all of the registered profiles and try to find a predecessor minor version (called the
    `baseline`) with profile of the same configuration (by configuration we mean the tuple of
    collector, postprocessors, command, arguments and workloads) and run the checks according to the
    rules set in the configurations.

    The rules are specified as an ordered list in the configuration by
    :ckey:`degradation.strategies`, where the keys correspond to the configuration (or the type) and
    key `method` specifies the actual method used for checking for performance changes. The applied
    methods can then be either specified by the full name or by its short string consisting of all
    first letter of the function name.

    The example of configuration snippet that sets rules and strategies for one project can be as
    follows:

      .. code-block:: yaml

      \b
          degradation:
            apply: first
            strategies:
              - type: mixed
                postprocessor: regression_analysis
                method: bmoe
              - cmd: mybin
                type: memory
                method: bmoe
              - method: aat

    Currently we support the following methods:

      \b
      1. Best Model Order Equality (BMOE)
      2. Average Amount Threshold (AAT)
    """
    should_precollect = dutils.strtobool(str(
        perun_config.lookup_key_recursively(
            'degradation.collect_before_check', 'false')
    ))
    precollect_to_log = dutils.strtobool(str(
        perun_config.lookup_key_recursively('degradation.log_collect', 'false')
    ))
    if should_precollect:
        print("{} is set to {}. ".format(
            termcolor.colored('degradation.collect_before_check',
                              'white', attrs=['bold']),
            termcolor.colored('true', 'green', attrs=['bold'])
        ), end='')
        print("Missing profiles will be freshly collected with respect to the ", end='')
        print("nearest job matrix (run `perun config edit` to modify the underlying job matrix).")
        if precollect_to_log:
            print("The progress of the pre-collect phase will be stored in logs at {}.".format(
                termcolor.colored(pcs.get_log_directory(),
                                  'white', attrs=['bold'])
            ))
        else:
            print("The progress of the pre-collect phase will be redirected to {}.".format(
                termcolor.colored('black hole', 'white', attrs=['bold'])
            ))


@check_group.command('head')
@click.argument('head_minor', required=False, metavar='<hash>', nargs=1,
                callback=cli_helpers.lookup_minor_version_callback, default='HEAD')
def check_head(head_minor='HEAD'):
    """Checks for changes in performance between between specified minor version (or current `head`)
    and its predecessor minor versions.

    The command iterates over all of the registered profiles of the specified `minor version`
    (`target`; e.g. the `head`), and tries to find the nearest predecessor minor version
    (`baseline`), where the profile with the same configuration as the tested target profile exists.
    When it finds such a pair, it runs the check according to the strategies set in the
    configuration (see :ref:`degradation-config` or :doc:`config`).

    By default the ``hash`` corresponds to the `head` of the current project.
    """
    print("")
    check.degradation_in_minor(head_minor)


@check_group.command('all')
@click.argument('minor_head', required=False, metavar='<hash>', nargs=1,
                callback=cli_helpers.lookup_minor_version_callback, default='HEAD')
def check_all(minor_head='HEAD'):
    """Checks for changes in performance for the specified interval of version history.

    The commands crawls through the whole history of project versions starting from the specified
    ``<hash>`` and for all of the registered profiles (corresponding to some `target` minor version)
    tries to find a suitable predecessor profile (corresponding to some `baseline` minor version)
    and runs the performance check according to the set of strategies set in the configuration
    (see :ref:`degradation-config` or :doc:`config`).
    """
    print("[!] Running the degradation checks on the whole VCS history. This might take a while!\n")
    check.degradation_in_history(minor_head)


@check_group.command('profiles')
@click.argument('baseline_profile', required=True, metavar='<baseline>', nargs=1,
                callback=cli_helpers.lookup_any_profile_callback)
@click.argument('target_profile', required=True, metavar='<target>', nargs=1,
                callback=cli_helpers.lookup_any_profile_callback)
@click.option('--minor', '-m', nargs=1, default=None, is_eager=True,
              callback=cli_helpers.lookup_minor_version_callback, metavar='<hash>',
              help='Will check the index of different minor version <hash>'
                   ' during the profile lookup.')
def check_profiles(baseline_profile, target_profile, minor, **_):
    """Checks for changes in performance between two profiles.

    The commands checks for the changes between two isolate profiles, that can be stored in pending
    profiles, registered in index, or be simply stored in filesystem. Then for the pair of profiles
    <baseline> and <target> the command runs the performance chekc according to the set of
    strategies set in the configuration (see :ref:`degradation-config` or :doc:`config`).

    <baseline> and <target> profiles will be looked up in the following steps:

        1. If profile is in form ``i@i`` (i.e, an `index tag`), then `ith`
           record registered in the minor version <hash> index will be used.

        2. If profile is in form ``i@p`` (i.e., an `pending tag`), then
           `ith` profile stored in ``.perun/jobs`` will be used.

        3. Profile is looked-up within the minor version <hash> index for a
           match. In case the <profile> is registered there, it will be used.

        4. Profile is looked-up within the ``.perun/jobs`` directory. In case
           there is a match, the found profile will be used.

        5. Otherwise, the directory is walked for any match. Each found match
           is asked for confirmation by user.

    """
    print("")
    check.degradation_between_files(baseline_profile, target_profile, minor)


@cli.group('utils')
def utils_group():
    """Contains set of developer commands, wrappers over helper scripts and other functions that are
    not the part of the main perun suite.
    """
    pass


@utils_group.command()
@click.argument('template_type', metavar='<template>', required=True,
                type=click.Choice(['collect', 'postprocess', 'view', 'check']))
@click.argument('unit_name', metavar='<unit>')
@click.option('--no-before-phase', '-nb', default=False, is_flag=True,
              help='If set to true, the unit will not have before() function defined.')
@click.option('--no-after-phase', '-na', default=False, is_flag=True,
              help='If set to true, the unit will not have after() function defined.')
@click.option('--author', nargs=1,
              help='Specifies the author of the unit')
@click.option('--no-edit', '-ne', default=False, is_flag=True,
              help='Will open the newly created files in the editor specified by '
                   ':ckey:`general.editor` configuration key.')
@click.option('--supported-type', '-st', 'supported_types', nargs=1, multiple=True,
              help="Sets the supported types of the unit (i.e. profile types).")
def create(template_type, **kwargs):
    """According to the given <template> constructs a new modules in Perun for <unit>.

    Currently this supports creating new modules for the tool suite (namely ``collect``,
    ``postprocess``, ``view``) or new algorithms for checking degradation (check). The command uses
    templates stored in `../perun/templates` directory and uses _jinja as a template handler. The
    templates can be parametrized by the following by options (if not specified 'none' is used).

    Unless ``--no-edit`` is set, after the successful creation of the files, an external editor,
    which is specified by :ckey:`general.editor` configuration key.

    .. _jinja: http://jinja2.pocoo.org/
    """
    try:
        scripts.create_unit_from_template(template_type, **kwargs)
    except ExternalEditorErrorException as editor_exception:
        perun_log.error("while invoking external editor: {}".format(
            str(editor_exception)))


def init_unit_commands(lazy_init=True):
    """Runs initializations for all of the subcommands (shows, collectors, postprocessors)

    Some of the subunits has to be dynamically initialized according to the registered modules,
    like e.g. show has different forms (raw, graphs, etc.).
    """
    for (unit, cli_cmd, cli_arg) in [(perun.view, show, 'show'),
                                     (perun.postprocess,
                                      postprocessby, 'postprocessby'),
                                     (perun.collect, collect, 'collect')]:
        if lazy_init and cli_arg not in sys.argv:
            continue
        for module in pkgutil.walk_packages(unit.__path__, unit.__name__ + '.'):
            # Skip modules, only packages can be used for show
            if not module[2]:
                continue
            unit_package = perun.utils.get_module(module[1])

            # Skip packages that are not for viewing, postprocessing, or collection of profiles
            if not hasattr(unit_package, 'SUPPORTED_PROFILES') and \
                    not hasattr(unit_package, 'COLLECTOR_TYPE'):
                continue

            # Skip those packages that do not contain the appropriate cli wrapper
            unit_module = perun.utils.get_module(module[1] + '.' + 'run')
            cli_function_name = module[1].split('.')[-1]
            if hasattr(unit_module, cli_function_name):
                cli_cmd.add_command(getattr(unit_module, cli_function_name))


# Initialization of other stuff
init_unit_commands()

if __name__ == "__main__":
    cli()
