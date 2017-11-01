"""Command Line Interface for the Perun performance control.

Simple Command Line Interface for the Perun functionality using the Click library,
calls underlying commands from the commands module.
"""

import os
import pkgutil
import re
import sys

import click
import perun.logic.commands as commands
import perun.logic.runner as runner
import perun.logic.store as store
from perun.logic.pcs import PCS

import perun.collect
import perun.logic.config as perun_config
import perun.postprocess
import perun.profile.factory as profiles
import perun.utils as utils
import perun.utils.log as perun_log
import perun.utils.streams as streams
import perun.vcs as vcs
import perun.view
from perun.utils.exceptions import UnsupportedModuleException, UnsupportedModuleFunctionException, \
    NotPerunRepositoryException, IncorrectProfileFormatException, EntryNotFoundException, \
    MissingConfigSectionException, InvalidConfigOperationException, VersionControlSystemException

__author__ = 'Tomas Fiedor'


@click.group()
@click.option('--no-pager', default=False, is_flag=True,
              help='Disables paging of the standard output (for log and status).')
@click.option('--verbose', '-v', count=True, default=0,
              help='Sets verbosity of the perun log')
def cli(verbose, no_pager):
    """Perun is a performance control system used to store profiles efficiently.

    Run 'perun init' to initialize your very first perun repository in the current directory.
    """
    # by default the pager is suppressed, and only calling it from the CLI enables it,
    # through --no-pager set by default to False you enable the paging
    perun_log.SUPPRESS_PAGING = no_pager

    # set the verbosity level of the log
    if perun_log.VERBOSITY < verbose:
        perun_log.VERBOSITY = verbose


def validate_key(ctx, _, value):
    """Validates the value of the key for the different modes.

    For get and set <key> is required, while for edit it has no effect.

    Arguments:
        ctx(click.Context): called context of the command line
        _(click.Option): called option (key in this case)
        value(object): assigned value to the <key> argument

    Returns:
        object: value for the <key> argument
    """
    operation = ctx.params['operation']
    if operation == 'edit' and value:
        perun_log.warn('setting <key> argument has no effect in edit config operation')
    elif operation in ('get', 'set') and not value:
        raise click.BadParameter("missing <key> argument for {} config operation".format(
            operation
        ))

    return value


def validate_value(ctx, _, value):
    """Validates the value parameter for different modes.

    Value is required for set operation, while in get and set has no effect.

    Arguments:
        ctx(click.Context): called context of the command line
        _(click.Option): called option (in this case value)
        value(object): assigned value to the <value> argument

    Returns:
        object: value for the <key> argument
    """
    operation = ctx.params['operation']
    if operation in ('edit', 'get') and value:
        perun_log.warn('setting <value> argument has no effect in {} config operation'.format(
            operation
        ))
    elif operation == 'set' and not value:
        raise click.BadParameter("missing <value> argument for set config operation")

    return value


@cli.command()
@click.argument('key', required=False, metavar='<key>', callback=validate_key)
@click.argument('value', required=False, metavar='<value>', callback=validate_value)
@click.option('--get', '-g', 'operation', is_eager=True, flag_value='get',
              help="Returns the value of the provided <key>.")
@click.option('--set', '-s', 'operation', is_eager=True, flag_value='set',
              help="Sets the value of the <key> to <value> in the configuration file.")
@click.option('--edit', '-e', 'operation', is_eager=True, flag_value='edit',
              help="Edits the configuration file in the user defined editor.")
@click.option('--local', '-l', 'store_type', flag_value='local',
              help='Sets the local config as working config (.perun/local.yml).')
@click.option('--shared', '-h', 'store_type', flag_value='shared',
              help='Sets the shared config as working config (shared.yml).')
@click.option('--nearest', '-n', 'store_type', flag_value='recursive', default=True,
              help='Recursively discover the nearest config (differs for modes).')
def config(**kwargs):
    """Get and set the options of local and global configurations.

    For each perun repository, there are two types of config:

        local.yml - this is local repository found in .perun directory, contains the
        local configuration with informations about wrapped repositories and job matrix
        used for quick generation of profiles (see 'perun run matrix --help' for more
        information about the syntax of local configuration for construction of job matrix).

        shared.yml - this is global repository for the system, which contains the information
        about perun repositories located throughout the system.

    The syntax of the key contains out of section separated by dots, where the first section
    represents the type of the config (either local or shared).

    Example usage:

        perun config --get local.vsc.type

            Retrieves the type of the wrapped repository of the local perun.
    """
    try:
        commands.config(**kwargs)
    except (MissingConfigSectionException, InvalidConfigOperationException) as mcs_err:
        perun_log.error(str(mcs_err))


def configure_local_perun(perun_path):
    """Configures the local perun repository with the interactive help of the user

    Arguments:
        perun_path(str): destination path of the perun repository
    """
    pcs = PCS(perun_path)
    editor = perun_config.lookup_key_recursively(pcs.path, 'global.editor')
    local_config_file = pcs.get_config_file('local')
    try:
        utils.run_external_command([editor, local_config_file])
    except ValueError as v_exception:
        perun_log.error("could not invoke '{}' editor: {}".format(editor, str(v_exception)))


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
              help="Apart of perun structure, a supported version control system can be wrapped"
                   " and initialized as well.")
@click.option('--vcs-path', metavar='<path>',
              help="Initializes the supported version control system at different path.")
@click.option('--vcs-param', nargs=2, metavar='<param>', multiple=True,
              callback=parse_vcs_parameter,
              help="Passes additional parameter to a supported version control system "
                   "initialization.")
@click.option('--vcs-flag', nargs=1, metavar='<flag>', multiple=True,
              callback=parse_vcs_parameter,
              help="Passes additional flags to a supported version control system initialization")
@click.option('--configure', '-c', is_flag=True, default=False,
              help='Opens the local configuration file for initial configuration edit.')
def init(dst, configure, **kwargs):
    """Initialize the new perun performance control system or reinitializes existing one.

    The command initializes the perun control system directory with basic directory and file
    structure inside the .perun directory. By default are created the following directories:

        \b
        /jobs---stores computed profiles, that are yet to be assigned to concrete minor versions
        /objects---stores packed contents and minor version informations
        /cache---stores number of unpacked profiles for quick access
        local.yml---local configuration file with job matrix, information about wrapped vcs, etc.

    Perun is initialized at <path>. If no <path> is given, then it is initialized within the
    current working directory. If there already exists a performance control system, file and
    directory structure is only reinitialized.

    By default, a custom version control system is initialized. This can be changed by stating
    the type of the wrapped control system using the --vcs-type parameter. Currently only git
    is supported. Additional parameters can be passed to the wrapped control system initialization
    using the --vcs-params.
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
    except PermissionError as perm_exp:
        assert 'shared.yml' in str(perm_exp)
        perun_log.error("writing to shared config 'shared.yml' requires root permissions")
    except MissingConfigSectionException:
        perun_log.error("cannot launch default editor for configuration.\n"
                        "Please set 'global.editor' key to a valid text editor (e.g. vim).")


def lookup_nth_pending_filename(position):
    """
    Arguments:
        position(int): position of the pending we will lookup

    Returns:
        str: pending profile at given position
    """
    pending = commands.get_untracked_profiles(PCS(store.locate_perun_dir_on(os.getcwd())))
    if 0 <= position < len(pending):
        return pending[position].id
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
              help='Perun will lookup the profile at different minor version (default is HEAD).')
@click.option('--keep-profile', is_flag=True, required=False, default=False,
              help='if set, then the added profile will not be deleted')
def add(profile, minor, **kwargs):
    """Assigns given profile to the concrete minor version storing its content in the perun dir.

    Takes the given <profile>, packs its content using the zlib compression module and stores it
    inside the perun objects directory. The packed profile is then registered within the minor
    version index represented by the <hash>.

    If no <hash> is given, then the HEAD of the wrapped control system is used instead.

    Example of adding profiles::

        \b
        perun add mybin-mcollect-input.txt-2017-03-01-16-11-04.perf

          Adds the profile collected by mcollect profile on mybin with input.txt workload computed
          on 1st March at 16:11 to the head.
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
              help='Perun will lookup the profile at different minor version (default is HEAD).')
@click.option('--remove-all', '-A', is_flag=True, default=False,
              help="Remove all occurrences of <profile> from the <hash> index.")
def rm(profile, minor, **kwargs):
    """Removes the given profile from the concrete minor version removing it from the index.

    Takes the given <profile>, looks it up at the <hash> minor version and removes it from the
    index. The contents of the profile are kept packed inside the objects directory.

    If no <hash> is given, then the HEAD of the wrapped control system is used instead.

    Examples of removing profiles::

        \b
        perun rm mybin-mcollect-input.txt-2017-03-01-16-11-04.perf

          Removes the profile collected by mcollect on mybin with input.txt from the workload
          computed on 1st March at 16:11 from the HEAD index
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
@click.option('--count-only', is_flag=True, default=False,
              help="Instead of showing list of all profiles, log will only show aggregated count of"
                   "profiles.")
@click.option('--show-aggregate', is_flag=True, default=False,
              help="Log will display the aggregated profile value for each minor version.")
@click.option('--last', default=1, metavar='<int>',
              help="Log will display only last <int> entries.")
@click.option('--no-merged', is_flag=True, default=False,
              help="Log will not display merges of minor versions.")
@click.option('--short', '-s', is_flag=True, default=False,
              help="Log will display a short version of the history.")
def log(head, **kwargs):
    """Prints the history of the the perun control system and its wrapped version control system.

    Prints the history of the wrapped version control system and all of the associated profiles
    starting from the <hash> point, printing the information about number of profiles, about
    concrete minor versions and its parents sorted by the date.

    In no <hash> is given, then HEAD of the version control system is used as a starting point.

    By default the long format is printed of the following form:

    \b
    Minor version <hash>
    <int> tracked profiles (<profile_type_numbers>)
    Author: <name> <email> <author_date>
    Parent: <hash>
    <desc>

    If --short | -s option is given, then the log is printed in the following short format,
    one entry per line:

    \b
    <hash> (<profile_numbers>) <short_info>
    """
    try:
        commands.log(head, **kwargs)
    except (NotPerunRepositoryException, UnsupportedModuleException) as exception:
        perun_log.error(str(exception))


@cli.command()
@click.option('--short', '-s', required=False, default=False, is_flag=True,
              help="Prints the status of the control systems using the short format.")
def status(**kwargs):
    """Shows the status of the perun control system and wrapped version control system.

    Shows the status of the both perun control system and wrapped version control system. Prints
    the current minor version head, current major version and description of the minor version.
    Moreover prints the list of tracked profiles lexicographically sorted along with their
    types and creation times.
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
              help='Perun will lookup the profile at different minor version (default is HEAD).')
@click.pass_context
def show(ctx, profile, **_):
    """Shows the profile stored and registered within the perun control system.

    Looks up the index of the given minor version and finds the <profile> and prints it
    to the command line. Either the profile is given as a .perf name, which is
    looked up within the index of the file or the hash is given, which represents
    the concrete object profile stored within perun.

    Example usage:

        perun show -c -o -m ddff3e echo-time-hello-2017-03-01-16-11-04.perf raw

            Shows the profile of the ddff3e minor version in raw format, coloured, summarized in
            one line.

        perun show echo-time-hello-2017-04-02-13-13-34-12.perf memory heap

            Shows the given profile of the current HEAD of the wrapped repository using as the heap
            map (if the profile is of memory type).
    """
    ctx.obj = profile
    # TODO: Check that if profile is not SHA-1, then minor must be set


@cli.group()
@click.argument('profile', required=True, metavar='<profile>', callback=profile_lookup_callback)
@click.option('--minor', '-m', nargs=1, default=None, is_eager=True,
              callback=minor_version_lookup_callback,
              help='Perun will lookup the profile at different minor version (default is HEAD).')
@click.pass_context
def postprocessby(ctx, profile, **_):
    """Postprocesses the profile stored and registered within the perun control system.

    Fixme: Default should not be head, but storage?

    Example usage:

        perun postprocessby echo-time-hello-2017-04-02-13-13-34-12.perf normalizer

            Postprocesses the profile echo-time-hello by normalizer, where for each snapshots,
            values of the resources will be normalized to the interval <0,1>.
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


@cli.group()
@click.option('--cmd', '-c', nargs=1, required=False, multiple=True, default=[''],
              help='Command that we will collect data from single collector.')
@click.option('--args', '-a', nargs=1, required=False, multiple=True,
              help='Additional arguments for the command.')
@click.option('--workload', '-w', nargs=1, required=False, multiple=True, default=[''],
              help='Inputs for the command, i.e. so called workloads.')
@click.option('--params', '-p', nargs=1, required=False, multiple=True,
              callback=parse_yaml_single_param,
              help='Additional parameters for called collector')
@click.pass_context
def collect(ctx, **kwargs):
    """Collect the profile from the given binary, arguments and workload"""
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
def run():
    """Run the jobs either using the job matrix or single command line command.

    Either runs the job matrix stored in local.yml configuration or lets the user
    construct the job run using the set of parameters.
    """


@run.command()
def matrix(**kwargs):
    """Runs the jobs matrix specified in the local.yml configuration.

    The job matrix is defined using the yaml configuration format and consists of specification
    of binaries with corresponding arguments, workloads, supported collectors of profiling data
    and postprocessors that alter the collected profiles.

    From the config file, a job matrix is constructed as a cartesian product of binaries with
    workloads and collectors. After each job the set of postprocessors are run.

    Example contents of the local.yml configuration file::

        \b
        bins:
          - ./mybin
          - ./otherbin

        \b
        workloads:
          - input.in
          - other_input.in

        \b
        collectors:
          - name: time

        \b
        postprocessors:
          - name: filter
          - name: normalizer

    This will run four jobs './mybin input.in', './mybin other_input.in', './otherbin input.in' and
    './otherbin other_input.in' with the time collector. Each collection will be afterwards post
    processed using the filter and normalizer postprocessors.

    For full documentation of the local.yml syntax consult the documentation.
    """
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
              help='Binary unit that we are collecting data for.')
@click.option('--args', '-a', nargs=1, required=False, multiple=True,
              help='Additional arguments for the binary unit.')
@click.option('--workload', '-w', nargs=1, required=False, multiple=True, default=[''],
              help='Inputs for the binary, i.e. so called workloads, that are run on binary.')
@click.option('--collector', '-c', nargs=1, required=True, multiple=True,
              type=click.Choice(utils.get_supported_module_names('collect')),
              help='Collector unit used to collect the profiling data for the binary.')
@click.option('--collector-params', '-cp', nargs=2, required=False, multiple=True,
              callback=parse_yaml_param,
              help='Parameters for the given collector read from the file in YAML format or'
                   'as a string..')
@click.option('--postprocessor', '-p', nargs=1, required=False, multiple=True,
              type=click.Choice(utils.get_supported_module_names('postprocess')),
              help='Additional postprocessing phases on profiles, after collection of the data.')
@click.option('--postprocessor-params', '-pp', nargs=2, required=False, multiple=True,
              callback=parse_yaml_param,
              help='Parameters for the given postprocessor read from the file in the YAML format or'
                   'as a string.')
def job(**kwargs):
    """Run specified batch of perun jobs to generate profiles.

    Computed profiles are stored inside the .perun/jobs/ directory as a files in form of:

        bin-collector-workload-timestamp.perf

    Profiles can be further stored in the perun control system using the command:

        perun add profile.perf

    Example runs:

        perun run job -c time -b ./mybin -w file.in -w file2.in -p normalizer

            Runs two jobs './mybin file.in' and './mybin file2.in' and collects the raw profile
            using the time collector. The profiles are afterwards normalized with the normalizer.

        perun run job -c comp-collect -b ./mybin -w sll.cpp -cp targetdir=./src

            Runs one job './mybin sll.cpp' using the comp-collect collector (note that comp-collect
            compiles custom binary from targetdir source)

        perun run job -c mcollect -b ./mybin -b ./otherbin -w input.txt -p normalizer -p filter

            Runs two jobs './mybin input.txt' and './otherbin input.txt' and collects the memory
            profile using the mcollect collector. The profiles are afterwards postprocessed,
            first using the normalizer and them with filter.
    """
    runner.run_single_job(**kwargs)


# Initialization of other stuff
init_unit_commands()

if __name__ == "__main__":
    cli()
