"""Command Line Interface for the Perun performance control.

Simple Command Line Interface for the Perun functionality using the Click library,
calls underlying commands from the commands module.
"""

import logging
import os
import pkgutil

import click

import perun.utils.log as perun_log
import perun.utils.streams as streams
import perun.core.logic.config as perun_config
import perun.core.logic.commands as commands
import perun.core.logic.runner as runner
import perun.collect
import perun.postprocess
import perun.view

from perun.utils.exceptions import UnsupportedModuleException, UnsupportedModuleFunctionException, \
    NotPerunRepositoryException, IncorrectProfileFormatException, EntryNotFoundException
from perun.utils.helpers import CONFIG_UNIT_ATTRIBUTES
from perun.core.logic.pcs import PCS

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


def register_unit(pcs, unit_name):
    """
    Arguments:
        pcs(PCS): perun repository wrapper
        unit_name(str): name of the unit
    """
    unit_params = CONFIG_UNIT_ATTRIBUTES[unit_name]

    perun_log.quiet_info("\nRegistering new {} unit".format(unit_name))
    if not unit_params:
        added_unit_name = click.prompt('name')
        # Add to config
        perun_config.append_key_at_config(pcs.local_config(), unit_name, added_unit_name)
    else:
        # Obtain each parameter for the given unit_name
        added_unit = {}
        for param in unit_params:
            if param.endswith('args'):
                param_value = click.prompt(param + "( -- separated list)")
            else:
                param_value = click.prompt(param)
            added_unit[param] = param_value.split(' -- ')
        # Append to config
        perun_config.append_key_at_config(pcs.local_config(), unit_name, added_unit)
    click.pause()


def unregister_unit(_):
    """Unregister the unit"""
    pass


def get_unit_list_from_config(perun_config, unit_type):
    """
    Arguments:
        perun_config(dict): dictionary config
        unit_type(str): type of the attribute we are getting

    Returns:
        list: list of units from config
    """
    unit_plural = unit_type + 's'
    is_iterable = unit_plural in ['collectors', 'postprocessors']

    if unit_plural in perun_config.keys():
        return [(unit_type, u.name if is_iterable else u) for u in perun_config[unit_plural]]
    else:
        return []


def list_units(pcs, do_confirm=True):
    """List the registered units inside the configuration of the perun in the following format.

    Unit_no. Unit [Unit_type]

    Arguments:
        pcs(PCS): perun repository wrapper
        do_confirm(bool): true if we should Press any key to continue
    """
    local_config = pcs.local_config().data
    units = []
    units.extend(get_unit_list_from_config(local_config, 'cmd'))
    units.extend(get_unit_list_from_config(local_config, 'workload'))
    units.extend(get_unit_list_from_config(local_config, 'collector'))
    units.extend(get_unit_list_from_config(local_config, 'postprocessor'))
    unit_list = list(enumerate(units))
    perun_log.quiet_info("")
    if not unit_list:
        perun_log.quiet_info("no units registered yet")
    else:
        for unit_no, (unit_type, unit_name) in unit_list:
            perun_log.quiet_info("{}. {} [{}]".format(unit_no, unit_name, unit_type))

    if do_confirm:
        click.pause()

    return unit_list


__config_functions__ = {
    'b': lambda pcs: register_unit(pcs, "bins"),
    'w': lambda pcs: register_unit(pcs, "workloads"),
    'c': lambda pcs: register_unit(pcs, "collectors"),
    'p': lambda pcs: register_unit(pcs, "postprocessors"),
    'l': list_units,
    'r': unregister_unit,
    'q': lambda pcs: exit(0)
}


def configure_local_perun(perun_path):
    """Configures the local perun repository with the interactive help of the user

    Arguments:
        perun_path(str): destination path of the perun repository
    """
    invalid_option_happened = False
    while True:
        click.clear()
        if invalid_option_happened:
            perun_log.warn("invalid option '{}'".format(option))
            invalid_option_happened = False
        perun_log.quiet_info("Welcome to the interactive configuration of Perun!")
        click.echo("[b] Register new binary/application run command")
        click.echo("[w] Register application workload")
        click.echo("[c] Register collector")
        click.echo("[p] Register postprocessor")
        click.echo("[l] List registered units")
        click.echo("[r] Remove registered unit")
        click.echo("[q] Quit")

        click.echo("\nAction:", nl=False)
        option = click.getchar()
        if option not in __config_functions__.keys():
            invalid_option_happened = True
            continue
        __config_functions__.get(option)(PCS(perun_path))


@cli.command()
@click.argument('dst', required=False, default=os.getcwd(), metavar='<path>')
# TODO: Add choice
@click.option('--vcs-type', metavar='<type>', default='pvcs',
              help="Apart of perun structure, a supported version control system can be wrapped"
                   " and initialized as well.")
@click.option('--vcs-path', metavar='<path>',
              help="Initializes the supported version control system at different path.")
@click.option('--vcs-params', metavar='<params>',
              help="Passes additional param to a supported version control system initialization.")
@click.option('--configure', '-c', is_flag=True, default=False,
              help='Runs the interactive initialization of the local configuration for the perun')
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


@cli.command()
@click.argument('profile', required=True, metavar='<profile>')
@click.argument('minor', required=False, default=None, metavar='<hash>')
def add(profile, minor):
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
        commands.add(profile, minor)
    except NotPerunRepositoryException as npre:
        perun_log.error(str(npre))
    except IncorrectProfileFormatException as ipfe:
        perun_log.error(str(ipfe))


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
    except NotPerunRepositoryException as npre:
        perun_log.error(str(npre))
    except EntryNotFoundException as enfe:
        perun_log.error(str(enfe))
    finally:
        perun_log.info("removed '{}'".format(profile))


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
@click.argument('profile', required=True, metavar='<profile>')
@click.option('--minor', '-m', nargs=1, default=None,
              help='Perun will lookup the profile at different minor version (default is HEAD).')
@click.pass_context
def show(ctx, profile, minor):
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
    # TODO: Check that if profile is not SHA-1, then minor must be set
    ctx.obj = commands.load_profile_from_args(profile, minor)
    perun_log.msg_to_stdout("Running 'perun show'", 2, logging.INFO)


@cli.group()
@click.argument('profile', required=True, metavar='<profile>')
@click.option('--minor', '-m', nargs=1, default=None,
              help='Perun will lookup the profile at different minor version (default is HEAD).')
@click.pass_context
def postprocessby(ctx, profile, minor):
    """Postprocesses the profile stored and registered within the perun control system.

    Fixme: Default should not be head, but storage?

    Example usage:

        perun postprocessby echo-time-hello-2017-04-02-13-13-34-12.perf normalizer

            Postprocesses the profile echo-time-hello by normalizer, where for each snapshots,
            values of the resources will be normalized to the interval <0,1>.
    """
    ctx.obj = commands.load_profile_from_args(profile, minor)
    perun_log.msg_to_stdout("Running 'perun postprocessby'", 2, logging.INFO)


@cli.group()
@click.option('--cmd', '-b', nargs=1, required=True, multiple=True,
              help='Command that we will collect data from single collector.')
@click.option('--args', '-a', nargs=1, required=False, multiple=True,
              help='Additional arguments for the command.')
@click.option('--workload', '-w', nargs=1, required=True, multiple=True,
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

            # Skip those packages that do not contain the apropriate cli wrapper
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


def parse_yaml_file_param(ctx, param, value):
    """Callback function for parsing the yaml files to dictionary object

    Fixme: Check for incorrect files and stuff

    Arguments:
        ctx(Context): context of the called command
        param(click.Option): parameter that is being parsed and read from commandline
        value(str): value that is being read from the commandline

    Returns:
        dict: parsed yaml file
    """
    unit_to_params = {}
    for (unit, yaml_file) in value:
        unit_to_params[unit] = streams.safely_load_yaml_from_file(yaml_file)
    return unit_to_params


def parse_yaml_string_param(ctx, param, value):
    """Callback function for parsing the yaml string to dictionary object

    Fixme: Check for incorrect strings

    Arguments:
        ctx(click.Context): context of the called command
        param(click.Option): parameter that is being parsed and read from commandline
        value(str): value that is being read from the commandline

    Returns:
        dict: parse yaml dictionary
    """
    unit_to_params = {}
    for (unit, yaml_string) in value:
        unit_to_params[unit] = streams.safely_load_yaml_from_stream(yaml_string)
    return unit_to_params


@run.command()
@click.option('--cmd', '-b', nargs=1, required=True, multiple=True,
              help='Binary unit that we are collecting data for.')
@click.option('--args', '-a', nargs=1, required=False, multiple=True,
              help='Additional arguments for the binary unit.')
@click.option('--workload', '-w', nargs=1, required=True, multiple=True,
              help='Inputs for the binary, i.e. so called workloads, that are run on binary.')
@click.option('--collector', '-c', nargs=1, required=True, multiple=True,
              help='Collector unit used to collect the profiling data for the binary.')
@click.option('--collector-params-from-string', '-cpfs', nargs=2, required=False, multiple=True,
              callback=parse_yaml_string_param,
              help='Parameters for the given collector supplied as a string.')
@click.option('--collector-params-from-file', '-cpff', nargs=2, required=False, multiple=True,
              callback=parse_yaml_file_param,
              help='Parameters for the given collector read from the file in YAML format.')
@click.option('--postprocessor', '-p', nargs=1, required=False, multiple=True,
              help='Additional postprocessing phases on profiles, after collection of the data.')
@click.option('--postprocessor-params-from-string', '-ppfs', nargs=2, required=False, multiple=True,
              callback=parse_yaml_string_param,
              help='Parameters for the given postprocessor supplied as a string.')
@click.option('--postprocessor-params-from-file', '-ppff', nargs=2, required=False, multiple=True,
              callback=parse_yaml_file_param,
              help='Parameters for the given postprocessor read from the file in the YAML format.')
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
    # TODO: Add choice to collector/postprocessors from the registered shits
    runner.run_single_job(**kwargs)


# Initialization of other stuff
init_unit_commands()

if __name__ == "__main__":
    cli()
