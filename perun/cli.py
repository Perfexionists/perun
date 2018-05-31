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
import re
import sys
import termcolor
import distutils.util as dutils

import click
import perun.logic.commands as commands
import perun.check.factory as check
import perun.logic.runner as runner
import perun.logic.store as store
from perun.logic.pcs import PCS

import perun.collect
import perun.logic.config as perun_config
import perun.postprocess
import perun.profile.factory as profiles
import perun.utils as utils
import perun.utils.script_helpers as scripts
import perun.utils.cli_helpers as cli_helpers
import perun.utils.log as perun_log
import perun.utils.streams as streams
import perun.vcs as vcs
import perun.view
from perun.utils.exceptions import UnsupportedModuleException, UnsupportedModuleFunctionException, \
    NotPerunRepositoryException, IncorrectProfileFormatException, EntryNotFoundException, \
    MissingConfigSectionException, ExternalEditorErrorException, VersionControlSystemException

__author__ = 'Tomas Fiedor'


def process_unsupported_option(_, param, value):
    """Processes the currently unsupported option.

    :param click.Context _: called context of the parameter
    :param click.Option param: parameter we are processing
    :param Object value: value of the parameter we are trying to set
    :return:  basically nothing
    """
    if value:
        perun_log.error("option '{}'".format(param.human_readable_name) +
                        "is unsupported/not implemented in this version of perun"
                        "\n\nPlease update your perun or wait patiently for the implementation")


@click.group()
@click.option('--no-pager', default=False, is_flag=True,
              help='Disable paging of the long standard output (currently'
              ' affects only ``status`` and ``log`` outputs). See '
              ':ckey:`paging` to change the default paging strategy.')
@click.option('--verbose', '-v', count=True, default=0,
              help='Increase the verbosity of the standard output. Verbosity '
              'is incremental, and each level increases the extent of output.')
def cli(verbose=0, no_pager=False):
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


def validate_key(_, param, value):
    """Validates whether the value of the key is in correct format---strings delimited by dot.

    Arguments:
        _(click.Context): called context of the command line
        param(click.Option): called option (key in this case)
        value(object): assigned value to the <key> argument

    Returns:
        object: value for the <key> argument
    """
    if not perun_config.is_valid_key(str(value)):
        raise click.BadParameter("<key> argument '{}' for {} config operation is in invalid format."
            "Valid key should be represented as sections delimited by dot (.),"
            " e.g. general.paging is valid key.".format(
                value, str(param.param_type_name)
            )
        )
    return value


@cli.group()
@click.option('--local', '-l', 'store_type', flag_value='local',
              help='Will lookup or set in the local config i.e. '
              '``.perun/local.yml``.')
@click.option('--shared', '-h', 'store_type', flag_value='shared',
              help='Will lookup or set in the shared config i.e. '
              '``shared.yml.``')
@click.option('--nearest', '-n', 'store_type', flag_value='recursive', default=True,
              help='Will recursively discover the nearest suitable config. The'
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
@click.argument('key', required=True, metavar='<key>', callback=validate_key)
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
        perun_log.error(str(mcs_err))


@config.command('set')
@click.argument('key', required=True, metavar='<key>', callback=validate_key)
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
        perun_log.error("could not invoke external editor: {}".format(str(editor_exception)))


def configure_local_perun(perun_path):
    """Configures the local perun repository with the interactive help of the user

    :param str perun_path: destination path of the perun repository
    :raises: ExternalEditorErrorException: when underlying editor makes any mistake
    """
    pcs = PCS(perun_path)
    editor = perun_config.lookup_key_recursively('general.editor')
    local_config_file = pcs.get_config_file('local')
    utils.run_external_command([editor, local_config_file])


def parse_vcs_parameter(ctx, param, value):
    """Parses flags and parameters for version control system during the init

    Collects all flags (as flag: True) and parameters (as key value pairs) inside the
    ctx.params['vcs_params'] dictionary, which is then send to the initialization of vcs.

    Arguments:
        ctx(Context): context of the called command
        param(click.Option): parameter that is being parsed
        value(str): value that is being read from the commandline

    Returns:
        tuple: tuple of flags or parameters
    """
    if 'vcs_params' not in ctx.params.keys():
        ctx.params['vcs_params'] = {}
    for v in value:
        if param.name.endswith("param"):
            ctx.params['vcs_params'][v[0]] = v[1]
        else:
            ctx.params['vcs_params'][v] = True
    return value


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
              callback=parse_vcs_parameter,
              help="Passes additional (key, value) parameter to initialization"
              " of version control system, e.g. ``separate-git-dir dir``.")
@click.option('--vcs-flag', nargs=1, metavar='<flag>', multiple=True,
              callback=parse_vcs_parameter,
              help="Passes additional flag to a initialization of version "
              "control system, e.g. ``bare``.")
@click.option('--configure', '-c', is_flag=True, default=False,
              help='After successful initialization of both systems, opens '
              'the local configuration using the :ckey:`editor` set in shared '
              'config.')
def init(dst, configure, **kwargs):
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
        commands.init(dst, **kwargs)

        if configure:
            # Run the interactive configuration of the local perun repository (populating .yml)
            configure_local_perun(dst)
        else:
            perun_log.quiet_info("\nIn order to automatically run jobs configure the matrix at:\n"
                                 "\n"
                                 + (" "*4) + ".perun/local.yml\n")
    except (UnsupportedModuleException, UnsupportedModuleFunctionException) as unsup_module_exp:
        perun_log.error(str(unsup_module_exp))
    except PermissionError:
        perun_log.error("writing to shared config 'shared.yml' requires root permissions")
    except (ExternalEditorErrorException, MissingConfigSectionException):
        perun_log.error("cannot launch default editor for configuration.\n"
                        "Please set 'general.editor' key to a valid text editor (e.g. vim).")


def lookup_nth_pending_filename(position):
    """
    Arguments:
        position(int): position of the pending we will lookup

    Returns:
        str: pending profile at given position
    """
    pending = commands.get_untracked_profiles(PCS(store.locate_perun_dir_on(os.getcwd())))
    profiles.sort_profiles(pending)
    if 0 <= position < len(pending):
        return pending[position].realpath
    else:
        raise click.BadParameter("invalid tag '{}' (choose from interval <{}, {}>)".format(
            "{}@p".format(position), '0@p', '{}@p'.format(len(pending)-1)
        ))


def added_filename_lookup_callback(ctx, param, value):
    """Callback function for looking up the profile, if it does not exist

    Arguments:
        ctx(Context): context of the called command
        param(click.Option): parameter that is being parsed and read from commandline
        value(str): value that is being read from the commandline

    Returns:
        str: filename of the profile
    """
    massaged_values = set()
    for single_value in value:
        match = store.PENDING_TAG_REGEX.match(single_value)
        if match:
            massaged_values.add(lookup_nth_pending_filename(int(match.group(1))))
        else:
            massaged_values.add(lookup_profile_filename(single_value))
    return massaged_values


def removed_filename_lookup_callback(ctx, param, value):
    """
    Arguments:
        ctx(Context): context of the called command
        param(click.Option): parameter that is being parsed and read from commandline
        value(str): value that is being read from the commandline

    Returns:
        str: filename of the profile to be removed
    """
    massaged_values = set()
    for single_value in value:
        match = store.INDEX_TAG_REGEX.match(single_value)
        if match:
            index_filename = commands.get_nth_profile_of(
                int(match.group(1)), ctx.params['minor']
            )
            start = index_filename.rfind('objects') + len('objects')
            # Remove the .perun/objects/... prefix and merge the directory and file to sha
            massaged_values.add("".join(index_filename[start:].split('/')))
        else:
            massaged_values.add(single_value)
    return massaged_values


def lookup_profile_filename(profile_name):
    """Callback function for looking up the profile, if it does not exist

    Arguments:
        profile_name(str): value that is being read from the commandline

    Returns:
        str: full path to profile
    """
    # 1) if it exists return the value
    if os.path.exists(profile_name):
        return profile_name

    perun_log.info("file '{}' does not exist. Checking pending jobs...".format(profile_name))
    # 2) if it does not exists check pending
    job_dir = PCS(store.locate_perun_dir_on(os.getcwd())).get_job_directory()
    job_path = os.path.join(job_dir, profile_name)
    if os.path.exists(job_path):
        return job_path

    perun_log.info("file '{}' not found in pending jobs...".format(profile_name))
    # 3) if still not found, check recursively all candidates for match and ask for confirmation
    searched_regex = re.compile(profile_name)
    for root, _, files in os.walk(os.getcwd()):
        for file in files:
            full_path = os.path.join(root, file)
            if file.endswith('.perf') and searched_regex.search(full_path):
                rel_path = os.path.relpath(full_path, os.getcwd())
                if click.confirm("did you perhaps mean '{}'?".format(rel_path)):
                    return full_path

    return profile_name


def minor_version_lookup_callback(ctx, param, value):
    """
    Arguments:
        ctx(Context): context of the called command
        param(click.Option): parameter that is being parsed and read from commandline
        value(str): value that is being read from the commandline

    Returns:
        str: massaged minor version
    """
    if value is not None:
        pcs = PCS(store.locate_perun_dir_on(os.getcwd()))
        try:
            return vcs.massage_parameter(pcs.vcs_type, pcs.vcs_path, value)
        except VersionControlSystemException as exception:
            raise click.BadParameter(str(exception))


@cli.command()
@click.argument('profile', required=True, metavar='<profile>', nargs=-1,
                callback=added_filename_lookup_callback)
@click.option('--minor', '-m', required=False, default=None, metavar='<hash>', is_eager=True,
              callback=minor_version_lookup_callback,
              help='<profile> will be stored at this minor version (default is HEAD).')
@click.option('--keep-profile', is_flag=True, required=False, default=False,
              help='Keeps the profile in filesystem after registering it in'
              ' Perun storage. Otherwise it is deleted.')
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

    <profile> can either be a ``pending tag`` or a fullpath. ``Pending tags``
    are in form of ``i@p``, where ``i`` stands for an index in the pending
    profile directory (i.e. ``.perun/jobs``) and ``@p`` is literal suffix.
    Run ``perun status`` to see the `tag` anotation of pending profiles.

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
        commands.add(profile, minor, **kwargs)
    except (NotPerunRepositoryException, IncorrectProfileFormatException) as exception:
        perun_log.error(str(exception))


@cli.command()
@click.argument('profile', required=True, metavar='<profile>', nargs=-1,
                callback=removed_filename_lookup_callback)
@click.option('--minor', '-m', required=False, default=None, metavar='<hash>', is_eager=True,
              callback=minor_version_lookup_callback,
              help='<profile> will be stored at this minor version (default is HEAD).')
@click.option('--remove-all', '-A', is_flag=True, default=False,
              help="Removes all occurrences of <profile> from the <hash> index.")
def rm(profile, minor, **kwargs):
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
    status`` to see the `tags` of current ``HEAD``'s index.

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
        perun_log.error(str(exception))
    finally:
        perun_log.info("removed '{}'".format(profile))


def profile_lookup_callback(ctx, _, value):
    """
    Arguments:
        ctx(click.core.Context): context
        _(click.core.Argument): param
        value(str): value of the profile parameter
    """
    # 0) First check if the value is tag or not
    index_tag_match = store.INDEX_TAG_REGEX.match(value)
    if index_tag_match:
        index_profile = commands.get_nth_profile_of(
            int(index_tag_match.group(1)), ctx.params['minor']
        )
        return profiles.load_profile_from_file(index_profile, is_raw_profile=False)

    pending_tag_match = store.PENDING_TAG_REGEX.match(value)
    if pending_tag_match:
        pending_profile = lookup_nth_pending_filename(int(pending_tag_match.group(1)))
        return profiles.load_profile_from_file(pending_profile, is_raw_profile=True)

    # 1) Check the index, if this is registered
    profile_from_index = commands.load_profile_from_args(value, ctx.params['minor'])
    if profile_from_index:
        return profile_from_index

    perun_log.info("file '{}' not found in index. Checking filesystem...".format(value))
    # 2) Else lookup filenames and load the profile
    abs_path = lookup_profile_filename(value)
    if not os.path.exists(abs_path):
        perun_log.error("could not find the file '{}'".format(abs_path))

    return profiles.load_profile_from_file(abs_path, is_raw_profile=True)


@cli.command()
@click.argument('head', required=False, default=None, metavar='<hash>')
# @click.option('--count-only', is_flag=True, default=False,
#               help="Shows only aggregated data without minor version history"
#               " description")
# @click.option('--show-aggregate', is_flag=True, default=False,
#               help="Includes the aggregated values for each minor version.")
# @click.option('--last', default=1, metavar='<int>',
#               help="Limits the output of log to last <int> entries.")
# @click.option('--no-merged', is_flag=True, default=False,
#               help="Skips merges during the iteration of the project history.")
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
        perun_log.error(str(exception))


@cli.command()
@click.option('--short', '-s', required=False, default=False, is_flag=True,
              help="Shortens the output of ``status`` to include only most"
              " necessary information.")
@click.option('--sort-by', '-sb', 'format__sort_profiles_by', nargs=1,
              type=click.Choice(profiles.ProfileInfo.valid_attributes),
              callback=cli_helpers.process_config_option,
              help="The stored and pending profiles will be sorted by <key>.")
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

    Refer to :ref:`logs-status` for information how to customize the outputs of
    ``status`` or how to set :ckey:`format.status` in nearest
    configuration.
    """
    try:
        commands.status(**kwargs)
    except (NotPerunRepositoryException, UnsupportedModuleException,
            MissingConfigSectionException) as exception:
        perun_log.error(str(exception))


@cli.group()
@click.argument('profile', required=True, metavar='<profile>', callback=profile_lookup_callback)
@click.option('--minor', '-m', nargs=1, default=None, is_eager=True,
              callback=minor_version_lookup_callback,
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
    # TODO: Check that if profile is not SHA-1, then minor must be set


def set_output_formatting_string(_, __, value):
    """Sets the value of the output_profile_template to the given value in the runtime
    configuration.

    :param click.Context _: called context of the parameter
    :param click.Option __: parameter we are processing
    :param Object value: concrete value of the object that we are storing
    :returns str: set string (though it is set in the runtime config as well)
    """
    if value:
        perun_config.runtime().set('format.output_profile_template', str(value))
    return value


@cli.group()
@click.argument('profile', required=True, metavar='<profile>', callback=profile_lookup_callback)
@click.option('--output-filename-template', '-ot', callback=set_output_formatting_string,
              default=None,
              help='Specifies the template for automatic generation of output filename'
              ' This way the postprocessed file will have a resulting filename w.r.t to this'
              ' parameter. Refer to :ckey:`format.output_profile_template` for more'
              ' details about the format of the template.')
@click.option('--minor', '-m', nargs=1, default=None, is_eager=True,
              callback=minor_version_lookup_callback,
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


def parse_yaml_single_param(ctx, param, value):
    """Callback function for parsing the yaml files to dictionary object, when called from 'collect'

    This does not require specification of the collector to which the params correspond and is
    meant as massaging of parameters for 'perun -p file collect ...' command.

    Arguments:
        ctx(Context): context of the called command
        param(click.Option): parameter that is being parsed and read from commandline
        value(str): value that is being read from the commandline

    Returns:
        dict: parsed yaml file
    """
    unit_to_params = {}
    for yaml_file in value:
        # First check if this is file
        if os.path.exists(yaml_file):
            unit_to_params.update(streams.safely_load_yaml_from_file(yaml_file))
        else:
            unit_to_params.update(streams.safely_load_yaml_from_stream(yaml_file))
    return unit_to_params


def parse_minor_version(ctx, _, value):
    """Callback function for parsing the minor version list for running the automation

    :param Context ctx: context of the called command
    :param click.Option _: parameter that is being parsed and read from commandline
    :param str value: value that is being read from the commandline
    :returns list: list of MinorVersion objects
    """
    minors = []
    if value:
        pcs = PCS(store.locate_perun_dir_on(os.getcwd()))
        for minor_version in value:
            massaged_version = vcs.massage_parameter(pcs.vcs_type, pcs.vcs_path, minor_version)
            # If we should crawl all of the parents, we collect them
            if ctx.params['crawl_parents']:
                minors.extend(vcs.walk_minor_versions(
                    pcs.vcs_type, pcs.vcs_path, massaged_version
                ))
            # Otherwise we retrieve the minor version info for the param
            else:
                minors.append(vcs.get_minor_version_info(
                    pcs.vcs_type, pcs.vcs_path, massaged_version
                ))
    return minors


@cli.group()
@click.option('--minor-version', '-m', 'minor_version_list', nargs=1, multiple=True,
              callback=parse_minor_version, default=['HEAD'],
              help='Specifies the head minor version, for which the profiles will be collected.')
@click.option('--crawl-parents', '-c', is_flag=True, default=False, is_eager=True,
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
              callback=parse_yaml_single_param,
              help='Additional parameters for called collector read from '
              'file in YAML format.')
@click.option('--output-filename-template', '-ot', callback=set_output_formatting_string,
              default=None,
              help='Specifies the template for automatic generation of output filename'
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


def init_unit_commands(lazy_init=True):
    """Runs initializations for all of the subcommands (shows, collectors, postprocessors)

    Some of the subunits has to be dynamically initialized according to the registered modules,
    like e.g. show has different forms (raw, graphs, etc.).
    """
    for (unit, cli_cmd, cli_arg) in [(perun.view, show, 'show'),
                                     (perun.postprocess, postprocessby, 'postprocessby'),
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
            if not hasattr(unit_module, cli_function_name):
                continue
            cli_cmd.add_command(getattr(unit_module, cli_function_name))


@cli.group()
@click.option('--output-filename-template', '-ot', callback=set_output_formatting_string,
              default=None,
              help='Specifies the template for automatic generation of output filename'
                   ' This way the file with collected data will have a resulting filename w.r.t '
                   ' to this parameter. Refer to :ckey:`format.output_profile_template` for more'
                   ' details about the format of the template.')
@click.option('--minor-version', '-m', 'minor_version_list', nargs=1, multiple=True,
              callback=parse_minor_version, default=['HEAD'],
              help='Specifies the head minor version, for which the profiles will be collected.')
@click.option('--crawl-parents', '-c', is_flag=True, default=False, is_eager=True,
              help='If set to true, then for each specified minor versions, profiles for parents'
                   ' will be collected as well')
@click.option('--force-dirty', '-f', is_flag=True, default=False,
              callback=process_unsupported_option,
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
def matrix(ctx, **kwargs):
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
    kwargs.update({'with_history': True})
    runner.run_matrix_job(**kwargs)


def parse_yaml_param(ctx, param, value):
    """Callback function for parsing the yaml files to dictionary object

    Arguments:
        ctx(Context): context of the called command
        param(click.Option): parameter that is being parsed and read from commandline
        value(str): value that is being read from the commandline

    Returns:
        dict: parsed yaml file
    """
    unit_to_params = {}
    for (unit, yaml_file) in value:
        # First check if this is file
        if os.path.exists(yaml_file):
            unit_to_params[unit] = streams.safely_load_yaml_from_file(yaml_file)
        else:
            unit_to_params[unit] = streams.safely_load_yaml_from_stream(yaml_file)
    return unit_to_params


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
              callback=parse_yaml_param,
              help='Additional parameters for the <collector> read from the'
              ' file in YAML format')
@click.option('--postprocessor', '-p', nargs=1, required=False, multiple=True,
              type=click.Choice(utils.get_supported_module_names('postprocess')),
              help='After each collection of data will run <postprocessor> to '
              'postprocess the collected resources.')
@click.option('--postprocessor-params', '-pp', nargs=2, required=False, multiple=True,
              callback=parse_yaml_param,
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
    :ref:`collectors-complexity`, which uses custom binaries targeted at
    ``./src`` directory.

    .. code-block:: bash

        perun run job -c mcollect -b ./mybin -b ./otherbin -w input.txt -p normalizer -p regression_analysis

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
    runner.run_single_job(**kwargs)


@cli.group('check')
@click.option('--compute-missing', '-c',
              callback=cli_helpers.set_runtime_option_from_flag(
                  'degradation.collect_before_check', True),
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
        perun_config.lookup_key_recursively('degradation.collect_before_check', 'false')
    ))
    precollect_to_log = dutils.strtobool(str(
        perun_config.lookup_key_recursively('degradation.log_collect', 'false')
    ))
    if should_precollect:
        print("{} is set to {}. ".format(
            termcolor.colored('degradation.collect_before_check', 'white', attrs=['bold']),
            termcolor.colored('true', 'green', attrs=['bold'])
        ), end='')
        print("Missing profiles will be freshly collected with respect to the ", end='')
        print("nearest job matrix (run `perun config edit` to modify the underlying job matrix).")
        if precollect_to_log:
            pcs = PCS(store.locate_perun_dir_on(os.getcwd()))
            print("The progress of the pre-collect phase will be stored in logs at {}.".format(
                termcolor.colored(pcs.get_log_directory(), 'white', attrs=['bold'])
            ))
        else:
            print("The progress of the pre-collect phase will be redirected to {}.".format(
                termcolor.colored('black hole', 'white', attrs=['bold'])
            ))


@check_group.command('head')
@click.argument('head_minor', required=False, metavar='<hash>', nargs=1,
                callback=minor_version_lookup_callback, default='HEAD')
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
                callback=minor_version_lookup_callback, default='HEAD')
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
                callback=profile_lookup_callback)
@click.argument('target_profile', required=True, metavar='<target>', nargs=1,
                callback=profile_lookup_callback)
@click.option('--minor', '-m', nargs=1, default=None, is_eager=True,
              callback=minor_version_lookup_callback, metavar='<hash>',
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
    templates stored in `..\perun\templates` directory and uses _jinja as a template handler. The
    templates can be parametrized by the following by options (if not specified 'none' is used).

    Unless ``--no-edit`` is set, after the successful creation of the files, an external editor,
    which is specified by :ckey:`general.editor` configuration key.

    .. _jinja: http://jinja2.pocoo.org/
    """
    try:
        scripts.create_unit_from_template(template_type, **kwargs)
    except ExternalEditorErrorException as editor_exception:
        perun_log.error("while invoking external editor: {}".format(str(editor_exception)))


# Initialization of other stuff
init_unit_commands()

if __name__ == "__main__":
    cli()
