"""Command Line Interface for the Perun performance control.

Simple Command Line Interface for the Perun functionality using the Click library,
calls underlying commands from the commands module.
"""

import logging
import os
import pkgutil
import re

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
    NotPerunRepositoryException, IncorrectProfileFormatException, EntryNotFoundException

__author__ = 'Tomas Fiedor'


@click.group()
@click.option('--verbose', '-v', count=True, default=0,
              help='sets verbosity of the perun log')
def cli(verbose):
    """Perun is a performance control system used to store profiles efficiently.

    Run 'perun init' to initialize your very first perun repository in the current directory.
    """
    # set the verbosity level of the log
    if perun_log.VERBOSITY < verbose:
        perun_log.VERBOSITY = verbose


@cli.command()
@click.argument('key', required=True)
@click.argument('value', required=False)
@click.option('--get', '-g', is_flag=True,
              help="get the value of the key")
@click.option('--set', '-s', is_flag=True,
              help="set the value of the key")
def config(key, value, **kwargs):
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
    perun_log.msg_to_stdout("Running 'perun config'", 2, logging.INFO)
    commands.config(key, value, **kwargs)


def configure_local_perun(perun_path):
    """Configures the local perun repository with the interactive help of the user

    Arguments:
        perun_path(str): destination path of the perun repository
    """
    pcs = PCS(perun_path)
    editor = perun_config.lookup_key_recursively(pcs.path, 'global.editor')
    local_config_file = os.path.join(pcs.path, 'local.yml')
    try:
        utils.run_external_command([editor, local_config_file])
    except ValueError as v_exception:
        perun_log.error("could not invoke '{}' editor: {}".format(editor, str(v_exception)))


@cli.command()
@click.argument('dst', required=False, default=os.getcwd(), metavar='<path>')
@click.option('--vcs-type', metavar='<type>', default='pvcs',
              type=click.Choice(utils.get_supported_module_names(vcs, '_init')),
              help="Apart of perun structure, a supported version control system can be wrapped"
                   " and initialized as well.")
@click.option('--vcs-path', metavar='<path>',
              help="Initializes the supported version control system at different path.")
@click.option('--vcs-params', metavar='<params>',
              help="Passes additional param to a supported version control system initialization.")
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
    perun_log.msg_to_stdout("Running 'perun init'", 2, logging.INFO)

    try:
        commands.init(dst, **kwargs)
    except (UnsupportedModuleException, UnsupportedModuleFunctionException) as unsup_module_exp:
        perun_log.error(str(unsup_module_exp))
    except PermissionError as perm_exp:
        # If this is problem with writing to shared.yml, say it is error and ask for sudo
        if 'shared.yml' in str(perm_exp):
            perun_log.error("writing to shared config 'shared.yml' requires root permissions")
        # Else reraise as who knows what kind of mistake is this
        else:
            raise perm_exp

    if configure:
        # Run the interactive configuration of the local perun repository (populating .yml)
        configure_local_perun(dst)
    else:
        perun_log.quiet_info("\nIn order to automatically run the jobs configure the matrix at:\n"
                             "\n"
                             + (" "*4) + ".perun/local.yml\n")


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


def filename_lookup_callback(ctx, param, value):
    """Callback function for looking up the profile, if it does not exist

    Arguments:
        ctx(Context): context of the called command
        param(click.Option): parameter that is being parsed and read from commandline
        value(str): value that is being read from the commandline

    Returns:
        str: filename of the profile
    """
    match = store.PENDING_TAG_REGEX.match(value)
    if match:
        return lookup_nth_pending_filename(int(match.group(1)))
    else:
        return lookup_profile_filename(value)


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


@cli.command()
@click.argument('profile', required=True, metavar='<profile>',
                callback=filename_lookup_callback)
@click.argument('minor', required=False, default=None, metavar='<hash>')
@click.option('--keep-profile', is_flag=True, required=False, default=False,
              help='if set, then the added profile will not be deleted')
def add(profile, minor, **kwargs):
    """Assigns given profile to the concrete minor version storing its content in the perun dir.

    Takes the given <profile>, packs its content using the zlib compression module and stores it
    inside the perun objects directory. The packed profile is then registered within the minor
    version index represented by the <hash>.

    If no <hash> is given, then the HEAD of the wrapped control system is used instead.

    Example of adding profiles:

        \b
        perun add mybin-mcollect-input.txt-2017-03-01-16-11-04.perf
          Adds the profile collected by mcollect profile on mybin with input.txt workload computed
          on 1st March at 16:11 to the head.
    """
    perun_log.msg_to_stdout("Running 'perun add'", 2, logging.INFO)

    try:
        commands.add(profile, minor, **kwargs)
    except (NotPerunRepositoryException, IncorrectProfileFormatException) as exception:
        perun_log.error(str(exception))


@cli.command()
@click.argument('profile', required=True, metavar='<profile>')
@click.argument('minor', required=False, default=None, metavar='<hash>')
@click.option('--remove-all', '-A', is_flag=True, default=False,
              help="Remove all occurrences of <profile> from the <hash> index.")
def rm(profile, minor, **kwargs):
    """Removes the given profile from the concrete minor version removing it from the index.

    Takes the given <profile>, looks it up at the <hash> minor version and removes it from the
    index. The contents of the profile are kept packed inside the objects directory.

    If no <hash> is given, then the HEAD of the wrapped control system is used instead.

    Examples of removing profiles:


        \b
        perun rm mybin-mcollect-input.txt-2017-03-01-16-11-04.perf
          Removes the profile collected by mcollect on mybin with input.txt from the workload
          computed on 1st March at 16:11 from the HEAD index
    """
    perun_log.msg_to_stdout("Running 'perun rm'", 2, logging.INFO)

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
        param(click.core.Argument): param
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
    perun_log.msg_to_stdout("Running 'perun log'", 2, logging.INFO)
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
    perun_log.msg_to_stdout("Running 'perun status'", 2, logging.INFO)
    try:
        commands.status(**kwargs)
    except (NotPerunRepositoryException, UnsupportedModuleException) as exception:
        perun_log.error(str(exception))


@cli.group()
@click.argument('profile', required=True, metavar='<profile>', callback=profile_lookup_callback)
@click.option('--minor', '-m', nargs=1, default=None, is_eager=True,
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
    perun_log.msg_to_stdout("Running 'perun show'", 2, logging.INFO)


@cli.group()
@click.argument('profile', required=True, metavar='<profile>', callback=profile_lookup_callback)
@click.option('--minor', '-m', nargs=1, default=None, is_eager=True,
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
    perun_log.msg_to_stdout("Running 'perun postprocessby'", 2, logging.INFO)


@cli.group()
@click.option('--cmd', '-c', nargs=1, required=True, multiple=True,
              help='Command that we will collect data from single collector.')
@click.option('--args', '-a', nargs=1, required=False, multiple=True,
              help='Additional arguments for the command.')
@click.option('--workload', '-w', nargs=1, required=False, multiple=True, default=[''],
              help='Inputs for the command, i.e. so called workloads.')
@click.pass_context
def collect(ctx, **kwargs):
    """Collect the profile from the given binary, arguments and workload"""
    ctx.obj = kwargs
    perun_log.msg_to_stdout("Running 'perun collect'", 2, logging.INFO)


def init_unit_commands():
    """Runs initializations for all of the subcommands (shows, collectors, postprocessors)

    Some of the subunits has to be dynamically initialized according to the registered modules,
    like e.g. show has different forms (raw, graphs, etc.).
    """
    for (unit, cli_cmd) in [(perun.view, show), (perun.postprocess, postprocessby),
                            (perun.collect, collect)]:
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
    perun_log.msg_to_stdout("Running 'perun run'", 2, logging.INFO)


@run.command()
def matrix(**kwargs):
    """Runs the jobs matrix specified in the local.yml configuration.

    The job matrix is defined using the yaml configuration format and consists of specification
    of binaries with corresponding arguments, workloads, supported collectors of profiling data
    and postprocessors that alter the collected profiles.

    From the config file, a job matrix is constructed as a cartesian product of binaries with
    workloads and collectors. After each job the set of postprocessors are run.

    Example contents of the local.yml configuration file:

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
              type=click.Choice(
                  utils.get_supported_module_names(perun.collect, 'COLLECTOR_TYPE')
              ),
              help='Collector unit used to collect the profiling data for the binary.')
@click.option('--collector-params', '-cp', nargs=2, required=False, multiple=True,
              callback=parse_yaml_param,
              help='Parameters for the given collector read from the file in YAML format or'
                   'as a string..')
@click.option('--postprocessor', '-p', nargs=1, required=False, multiple=True,
              type=click.Choice(
                  utils.get_supported_module_names(perun.postprocess, 'SUPPORTED_PROFILES')
              ),
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
