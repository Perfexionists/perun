"""Commands is a core of the perun implementation containing the basic commands.

Commands contains implementation of the basic commands of perun pcs. It is meant
to be run both from GUI applications and from CLI, where each of the function is
possible to be run in isolation.
"""

import inspect
import os
import termcolor
from colorama import init

import perun.utils.decorators as decorators
import perun.utils.log as perun_log
import perun.core.logic.config as perun_config
import perun.core.logic.profile as profile
import perun.core.logic.runner as runner
import perun.core.logic.store as store
import perun.core.vcs as vcs
import perun.view as view

from perun.utils.helpers import MAXIMAL_LINE_WIDTH, \
    TEXT_EMPH_COLOUR, TEXT_ATTRS, TEXT_WARN_COLOUR, \
    PROFILE_TYPE_COLOURS, PROFILE_MALFORMED, SUPPORTED_PROFILE_TYPES, \
    HEADER_ATTRS, HEADER_COMMIT_COLOUR, HEADER_INFO_COLOUR, HEADER_SLASH_COLOUR, \
    Job, COLLECT_PHASE_BIN, COLLECT_PHASE_COLLECT, COLLECT_PHASE_POSTPROCESS, \
    COLLECT_PHASE_WORKLOAD, COLLECT_PHASE_ATTRS, COLLECT_PHASE_ATTRS_HIGH, \
    CollectStatus, PostprocessStatus
from perun.core.logic.pcs import PCS

# Init colorama for multiplatform colours
init()


def find_perun_dir_on_path(path):
    """Locates the nearest perun directory

    Locates the nearest perun directory starting from the @p path. It walks all of the
    subpaths sorted by their lenght and checks if .perun directory exists there.

    Arguments:
        path(str): starting point of the perun dir search

    Returns:
        str: path to perun dir or "" if the path is not underneath some underlying perun control
    """
    # convert path to subpaths and reverse the list so deepest subpaths are traversed first
    lookup_paths = store.path_to_subpath(path)[::-1]

    for tested_path in lookup_paths:
        assert os.path.isdir(tested_path)
        if '.perun' in os.listdir(tested_path):
            return tested_path
    return ""


def pass_pcs(func):
    """Decorator for passing pcs object to function

    Provided the current working directory, constructs the PCS object,
    that encapsulates the performance control and passes it as argument.

    Note: Used for CLI interface.

    Arguments:
        func(function): function we are decorating

    Returns:
        func: wrapped function
    """
    def wrapper(*args, **kwargs):
        """Wrapper function for the decorator"""
        perun_directory = find_perun_dir_on_path(os.getcwd())
        return func(PCS(perun_directory), *args, **kwargs)

    return wrapper


def lookup_minor_version(func):
    """If the minor_version is not given by the caller, it looks up the HEAD in the repo.

    If the @p func is called with minor_version parameter set to None,
    then this decorator performs a lookup of the minor_version corresponding
    to the head of the repository.

    Arguments:
        func(function): decorated function for which we will lookup the minor_version

    Returns:
        function: decorated function, with minor_version translated or obtained
    """
    # the position of minor_version is one less, because of  needed pcs parameter
    f_args, _, _, f_defaults, *_ = inspect.getfullargspec(func)
    assert 'pcs' in f_args
    minor_version_position = f_args.index('minor_version') - 1

    def wrapper(pcs, *args, **kwargs):
        """Inner wrapper of the function"""
        # if the minor_version is None, then we obtain the minor head for the wrapped type
        if minor_version_position < len(args) and args[minor_version_position] is None:
            # note: since tuples are immutable we have to do this workaround
            arg_list = list(args)
            arg_list[minor_version_position] = vcs.get_minor_head(
                pcs.vcs_type, pcs.vcs_path)
            args = tuple(arg_list)
        return func(pcs, *args, **kwargs)

    return wrapper


def is_valid_config_key(key):
    """Key is valid if it starts either with local. or global.

    Arguments:
        key(str): key representing the string

    Returns:
        bool: true if the key is valid config key
    """
    return key.startswith('local.') or key.startswith('global.')


def proper_combination_is_set(kwargs):
    """Checks that only one command (--get or --set) is given

    Arguments:
        kwargs(dict): dictionary of key arguments.

    Returns:
        bool: true if proper combination of arguments is set for configuration
    """
    return kwargs['get'] != kwargs['set'] and any([kwargs['get'], kwargs['set']])


@pass_pcs
@decorators.validate_arguments(['key'], is_valid_config_key)
@decorators.validate_arguments(['kwargs'], proper_combination_is_set)
def config(pcs, key, value, **kwargs):
    """Updates the configuration file @p config of the @p pcs perun file

    Arguments:
        pcs(PCS): object with performance control system wrapper
        key(str): key that is looked up or stored in config
        value(str): value we are setting to config
        kwargs(dict): dictionary of keyword arguments
    """
    perun_log.msg_to_stdout("Running inner 'perun config' with {}, {}, {}, {}".format(
        pcs, key, value, kwargs
    ), 2)

    # TODO: Refactor this
    config_type, *sections = key.split('.')
    key = ".".join(sections)

    config_store = pcs.local_config() if config_type == 'local' else pcs.global_config()

    if kwargs['get']:
        value = perun_config.get_key_from_config(config_store, key)
        print("{}: {}".format(key, value))
    elif kwargs['set']:
        perun_config.set_key_at_config(config_store, key, value)
        print("Value '{1}' set for key '{0}'".format(key, value))


def init_perun_at(perun_path, init_custom_vcs, is_reinit, vcs_config):
    """Initialize the .perun directory at given path

    Initializes or reinitializes the .perun directory at the given path.
    Additionaly, if init_custom_vcs is set to true, the custom version control
    system is initialized as well.

    Arguments:
        perun_path(path): path where new perun performance control system will be stored
        init_custom_vcs(bool): true if the custom vcs should be initialized as well
        is_reinit(bool): true if this is existing perun, that will be reinitialized
        vcs_config(dict): dictionary of form {'vcs': {'type', 'url'}} for local config init
    """
    # Initialize the basic structure of the .perun directory
    perun_full_path = os.path.join(perun_path, '.perun')
    store.touch_dir(perun_full_path)
    store.touch_dir(os.path.join(perun_full_path, 'objects'))
    store.touch_dir(os.path.join(perun_full_path, 'jobs'))
    store.touch_dir(os.path.join(perun_full_path, 'cache'))
    perun_config.init_local_config_at(perun_full_path, vcs_config)

    # Initialize the custom (manual) version control system
    if init_custom_vcs:
        custom_vcs_path = os.path.join(perun_full_path, 'vcs')
        store.touch_dir(custom_vcs_path)
        store.touch_dir(os.path.join(custom_vcs_path, 'objects'))
        store.touch_dir(os.path.join(custom_vcs_path, 'tags'))
        store.touch_file(os.path.join(custom_vcs_path, 'HEAD'))

    # Perun successfully created
    msg_prefix = "Reinitialized existing" if is_reinit else "Initialized empty"
    perun_log.msg_to_stdout(msg_prefix + " Perun repository in {}".format(perun_path), 0)


def init(dst, **kwargs):
    """Initializes the performance and version control systems

    Inits the performance control system at a given directory. Optionally inits the
    wrapper of the Version Control System that is used as tracking point.

    Arguments:
        dst(path): path where the pcs will be initialized
        pcs(PCS): object with performance control system wrapper
    """
    perun_log.msg_to_stdout("call init({}, {})".format(dst, kwargs), 2)

    # Construct local config
    vcs_config = {
        'vcs': {
            'url': kwargs['vcs_path'] or "../",
            'type': kwargs['vcs_type'] or 'pvcs'
        }
    }

    # check if there exists perun directory above and initialize the new pcs
    super_perun_dir = find_perun_dir_on_path(dst)
    is_reinit = (super_perun_dir == dst)

    if not is_reinit and super_perun_dir != "":
        perun_log.warn("There exists super perun directory at {}".format(super_perun_dir))
    init_perun_at(dst, kwargs['vcs_type'] == 'pvcs', is_reinit, vcs_config)

    # register new performance control system in config
    if not is_reinit:
        global_config = perun_config.shared()
        perun_config.append_key_at_config(global_config, 'pcs', {'dir': dst})

    # Init the wrapping repository as well
    if kwargs['vcs_type'] is not None:
        if not kwargs['vcs_path']:
            kwargs['vcs_path'] = PCS(dst).vcs_path
        if not vcs.init(kwargs['vcs_type'], kwargs['vcs_path'], kwargs['vcs_params']):
            perun_log.error("Could not initialize empty {} repository at {}".format(
                kwargs['vcs_type'], kwargs['vcs_path']
            ))


@pass_pcs
@lookup_minor_version
def add(pcs, profile_name, minor_version):
    """Appends @p profile to the @p minor_version inside the @p pcs

    Arguments:
        pcs(PCS): object with performance control system wrapper
        profile_name(Profile): profile that will be stored for the minor version
        minor_version(str): SHA-1 representation of the minor version
    """
    assert minor_version is not None and "Missing minor version specification"

    perun_log.msg_to_stdout("Running inner wrapper of the 'perun add' with args {}, {}, {}".format(
        pcs, profile_name, minor_version
    ), 2)

    # Test if the given profile exists
    if not os.path.exists(profile_name):
        perun_log.error("{} does not exists".format(profile_name))

    # Load profile content
    with open(profile_name, 'r', encoding='utf-8') as profile_handle:
        profile_content = "".join(profile_handle.readlines())

        # Unpack to JSON representation
        unpacked_profile = profile.load_profile_from_file(profile_name, True)
        assert 'type' in unpacked_profile['header'].keys()

    # Append header to the content of the file
    header = "profile {} {}\0".format(unpacked_profile['header']['type'], len(profile_content))
    profile_content = (header + profile_content).encode('utf-8')

    # Transform to internal representation - file as sha1 checksum and content packed with zlib
    profile_sum = store.compute_checksum(profile_content)
    compressed_content = store.pack_content(profile_content)

    # Add to control
    store.add_loose_object_to_dir(pcs.get_object_directory(), profile_sum, compressed_content)

    # Register in the minor_version index
    store.register_in_index(pcs.get_object_directory(), minor_version, profile_name, profile_sum)


@pass_pcs
@lookup_minor_version
def remove(pcs, profile_name, minor_version, **kwargs):
    """Removes @p profile from the @p minor_version inside the @p pcs

    Arguments:
        pcs(PCS): object with performance control system wrapper
        profile_name(Profile): profile that will be stored for the minor version
        minor_version(str): SHA-1 representation of the minor version
        kwargs(dict): dictionary with additional options
    """
    assert minor_version is not None and "Missing minor version specification"

    perun_log.msg_to_stdout("Running inner wrapper of the 'perun rm'", 2)

    object_directory = pcs.get_object_directory()
    store.remove_from_index(object_directory, minor_version, profile_name, kwargs['remove_all'])


def print_short_minor_info_header():
    """Prints short header for the --short-minor option"""
    # Print left column---minor versions
    print(termcolor.colored(
        "minor  ", HEADER_COMMIT_COLOUR, attrs=HEADER_ATTRS
    ), end='')

    # Print middle column---profile number info
    slash = termcolor.colored('/', HEADER_SLASH_COLOUR, attrs=HEADER_ATTRS)
    end_msg = termcolor.colored(' profiles) ', HEADER_SLASH_COLOUR, attrs=HEADER_ATTRS)
    print(termcolor.colored(" ({0}{4}{1}{4}{2}{4}{3}{5}".format(
        termcolor.colored('a', HEADER_COMMIT_COLOUR, attrs=HEADER_ATTRS),
        termcolor.colored('m', PROFILE_TYPE_COLOURS['memory'], attrs=HEADER_ATTRS),
        termcolor.colored('x', PROFILE_TYPE_COLOURS['mixed'], attrs=HEADER_ATTRS),
        termcolor.colored('t', PROFILE_TYPE_COLOURS['time'], attrs=HEADER_ATTRS),
        slash,
        end_msg
    ), HEADER_SLASH_COLOUR, attrs=HEADER_ATTRS), end='')

    # Print right column---minor version one line details
    print(termcolor.colored(
        "info".ljust(MAXIMAL_LINE_WIDTH, ' '), HEADER_INFO_COLOUR, attrs=HEADER_ATTRS
    ))


def print_profile_number_for_minor(base_dir, minor_version, ending='\n'):
    """Print the number of tracked profiles corresponding to the profile

    Arguments:
        base_dir(str): base directory for minor version storage
        minor_version(str): minor version we are printing the info for
        ending(str): ending of the print (for different output of log and status)
    """
    tracked_profiles = store.get_profile_number_for_minor(base_dir, minor_version)
    if tracked_profiles['all']:
        print("{0[all]} tracked profiles (".format(tracked_profiles), end='')
        first_outputed = False
        for profile_type in SUPPORTED_PROFILE_TYPES:
            if not tracked_profiles[profile_type]:
                continue
            if first_outputed:
                print(', ', end='')
            print(termcolor.colored("{0} {1}".format(
                tracked_profiles[profile_type], profile_type
            ), PROFILE_TYPE_COLOURS[profile_type]), end='')
            first_outputed = True
        print(')', end=ending)
    else:
        print(termcolor.colored('(no tracked profiles)', TEXT_WARN_COLOUR, attrs=TEXT_ATTRS),
              end='\n')


@pass_pcs
@lookup_minor_version
def log(pcs, minor_version, **kwargs):
    """Prints the log of the @p pcs

    Arguments:
        pcs(PCS): object with performance control system wrapper
        minor_version(str): representation of the head version
        kwargs(dict): dictionary of the additional parameters
    """
    perun_log.msg_to_stdout("Running inner wrapper of the 'perun log '", 2)

    # Print header for --short-minors
    if kwargs['short']:
        print_short_minor_info_header()

    # Walk the minor versions and print them
    for minor in vcs.walk_minor_versions(pcs.vcs_type, pcs.vcs_path, minor_version):
        if kwargs['short']:
            print_short_minor_version_info(pcs, minor)
        else:
            print(termcolor.colored("Minor Version {}".format(
                minor.checksum
            ), TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS))
            print_profile_number_for_minor(pcs.get_object_directory(), minor.checksum)
            print_minor_version_info(minor, 1)


def print_short_minor_version_info(pcs, minor_version):
    """
    Arguments:
        pcs(PCS): object with performance control system wrapper
        minor_version(MinorVersion): minor version object
    """
    tracked_profiles = store.get_profile_number_for_minor(
        pcs.get_object_directory(), minor_version.checksum
    )
    short_checksum = minor_version.checksum[:6]
    print(termcolor.colored("{}  ".format(
        short_checksum
    ), TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS), end='')

    if tracked_profiles['all']:
        print(termcolor.colored("(", HEADER_INFO_COLOUR, attrs=TEXT_ATTRS), end='')
        print(termcolor.colored("{}".format(
            tracked_profiles['all']
        ), TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS), end='')

        # Print the coloured numbers
        for profile_type in SUPPORTED_PROFILE_TYPES:
            print("{}{}".format(
                termcolor.colored('/', HEADER_SLASH_COLOUR),
                termcolor.colored("{}".format(
                    tracked_profiles[profile_type]
                ), PROFILE_TYPE_COLOURS[profile_type])
            ), end='')

        print(termcolor.colored(" profiles)", HEADER_INFO_COLOUR, attrs=TEXT_ATTRS), end='')
    else:
        print(termcolor.colored('---no--profiles---', TEXT_WARN_COLOUR, attrs=TEXT_ATTRS), end='')

    short_description = minor_version.desc.split("\n")[0].ljust(MAXIMAL_LINE_WIDTH)
    if len(short_description) > MAXIMAL_LINE_WIDTH:
        short_description = short_description[:MAXIMAL_LINE_WIDTH-3] + "..."
    print(" {0} ".format(short_description))


def print_minor_version_info(head_minor_version, indent=0):
    """
    Arguments:
        head_minor_version(str): identification of the commit (preferably sha1)
        indent(int): indent of the description part
    """
    print("Author: {0.author} <{0.email}> {0.date}".format(head_minor_version))
    for parent in head_minor_version.parents:
        print("Parent: {}".format(parent))
    print("")
    indented_desc = '\n'.join(map(
        lambda line: ' '*(indent*4) + line, head_minor_version.desc.split('\n')
    ))
    print(indented_desc)


def print_minor_version_profiles(pcs, minor_version):
    """
    Arguments:
        pcs(PCS): performance control system
        minor_version(str): identification of the commit (preferably sha1)
    """
    profiles = store.get_profile_list_for_minor(pcs.get_object_directory(), minor_version)
    print_profile_number_for_minor(pcs.get_object_directory(), minor_version, ':\n\n')

    # Compute the padding and peek the types between
    profile_tuples = []
    maximal_type_len = maximal_profile_name_len = 0
    for index_entry in profiles:
        _, profile_name = store.split_object_name(pcs.get_object_directory(), index_entry.checksum)
        profile_type = store.peek_profile_type(profile_name)

        if len(index_entry.path) > maximal_profile_name_len:
            maximal_profile_name_len = len(index_entry.path)

        if len(profile_type) > maximal_type_len:
            maximal_type_len = len(profile_type)

        profile_tuples.append((profile_type, index_entry))

    # Print with padding
    for profile_type, index_entry in profile_tuples:
        print("\t{2} {0} ({1})".format(
            index_entry.path.ljust(maximal_profile_name_len),
            index_entry.time,
            termcolor.colored(
                "[{}]".format(profile_type).ljust(maximal_type_len+2),
                PROFILE_TYPE_COLOURS[profile_type], attrs=TEXT_ATTRS,
            )
        ))


@pass_pcs
def status(pcs, **kwargs):
    """Prints the status of performance control system

    Arguments:
        pcs(PCS): performance control system
        kwargs(dict): dictionary of keyword arguments
    """
    # Get major head and print the status.
    major_head = vcs.get_head_major_version(pcs.vcs_type, pcs.vcs_path)
    print("On major version {} ".format(
        termcolor.colored(major_head, TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS)
    ), end='')

    # Print the index of the current head
    minor_head = vcs.get_minor_head(pcs.vcs_type, pcs.vcs_path)
    print("(minor version: {})".format(
        termcolor.colored(minor_head, TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS)
    ))

    # Print in long format, the additional information about head commit
    print("")
    if not kwargs['short']:
        minor_version = vcs.get_minor_version_info(pcs.vcs_type, pcs.vcs_path, minor_head)
        print_minor_version_info(minor_version)

    # Print profiles
    print_minor_version_profiles(pcs, minor_head)


@pass_pcs
@lookup_minor_version
def show(pcs, profile_name, minor_version, **kwargs):
    """
    Arguments:
        pcs(PCS): object with performance control system wrapper
        profile_name(Profile): profile that will be stored for the minor version
        minor_version(str): SHA-1 representation of the minor version
        kwargs(dict): keyword atributes containing additional options
    """
    perun_log.msg_to_stdout("Running inner wrapper of the 'perun show'", 2)

    # If the profile is in raw form
    if not store.is_sha1(profile_name):
        _, minor_index_file = store.split_object_name(pcs.get_object_directory(), minor_version)
        if not os.path.exists(minor_index_file):
            perun_log.error("{} index has no profiles registered".format(profile_name, minor_version))
        with open(minor_index_file, 'rb') as minor_handle:
            lookup_pred = lambda entry: entry.path == profile_name
            profiles = store.lookup_all_entries_within_index(minor_handle, lookup_pred)
    else:
        profiles = [profile_name]

    # If there are more profiles we should chose
    if not profiles:
        perun_log.error("{} is not registered in {} index".format(profile_name, minor_version))
    chosen_profile = profiles[0]

    # Peek the type if the profile is correct and load the json
    _, profile_name = store.split_object_name(pcs.get_object_directory(), chosen_profile.checksum)
    profile_type = store.peek_profile_type(profile_name)
    if profile_type == PROFILE_MALFORMED:
        perun_log.error("malformed profile {}".format(profile_name))
    loaded_profile = profile.load_profile_from_file(profile_name, False)

    # Show the profile using the format
    if kwargs['coloured']:
        view.show_coloured(kwargs['format'], loaded_profile)
    else:
        view.show(kwargs['format'], loaded_profile)


def construct_job_matrix(bin, args, workload, collector, postprocessor):
    """Constructs the job matrix represented as dictionary.

    Reads the local of the current PCS and constructs the matrix of jobs
    that will be run. Each job consists of command that will be run,
    collector used to collect the data and list of postprocessors to
    alter the output profiles. Inside the dictionary jobs are distributed
    by binaries, then workloads and finally Jobs.

    Returns the job matrix as dictionary of form:
    {
      'bin1': {
        'workload1': [ Job1, Job2 , ...],
        'workload2': [ Job1, Job2 , ...]
      },
      'bin2': {
        'workload1': [ Job1, Job2 , ...],
        'workload2': [ Job1, Job2 , ...]
      }
    }

    Arguments:
        bin(str): binary that will be run
        args(str): lists of additional arguments to the job
        workload(list): list of workloads
        collector(list): list of collectors
        postprocessor(list): list of postprocessors

    Returns:
        dict, int: dict of jobs in form of {bins: {workloads: {Job}}}, number of jobs
    """
    matrix = {
        b: {
            w: [
                Job(c, postprocessor, b, w, a) for c in collector for a in args or ['']
            ] for w in workload
        } for b in bin
    }

    # Count overall number of the jobs:
    number_of_jobs = 0
    for bin_values in matrix.values():
        for workload_values in bin_values.values():
            for job in workload_values:
                number_of_jobs += 1 + len(job.postprocessors)

    return matrix, number_of_jobs


@decorators.static_variables(current_job=1)
def print_job_progress(overall_jobs):
    """Print the tag with the percent of the jobs currently done

    Arguments:
        overall_jobs(int): overall number of jobs to be done
    """
    percentage_done = round((print_job_progress.current_job / overall_jobs) * 100)
    print("[{}%] ".format(
        str(percentage_done).rjust(3, ' ')
    ), end='')
    print_job_progress.current_job += 1


def print_current_phase(phase_msg, phase_unit, phase_colour):
    """Print helper coloured message for the current phase

    Arguments:
        phase_msg(str): message that will be printed to the output
        phase_unit(str): additional parameter that is passed to the phase_msg
        phase_colour(str): phase colour defined in helpers.py
    """
    print(termcolor.colored(
        phase_msg.format(
            termcolor.colored(phase_unit, attrs=COLLECT_PHASE_ATTRS_HIGH)
        ), phase_colour, attrs=COLLECT_PHASE_ATTRS
    ))


@pass_pcs
def run_single_job(pcs, bin, args, workload, collector, postprocessor):
    """
    Arguments:
        pcs(PCS): object with performance control system wrapper
        bin(str): binary that will be run
        args(str): lists of additional arguments to the job
        workload(list): list of workloads
        collector(list): list of collectors
        postprocessor(list): list of postprocessors
    """
    job_matrix, number_of_jobs = construct_job_matrix(bin, args, workload, collector, postprocessor)
    run_jobs(pcs, job_matrix, number_of_jobs)


def load_job_info_from_config(pcs):
    """
    Arguments:
        pcs(PCS): object with performance control system wrapper

    Returns:
        dict: dictionary with bins, args, workloads, collectors and postprocessors
    """
    def join_command(command):
        """
        Arguments:
            command(dict): command we are joining (containing 'name' and 'params')

        Returns:
            str: joined string
        """
        if 'params' in command.keys():
            return " ".join([command['name'], str(command['params'])])
        else:
            return command['name']

    local_config = pcs.local_config().data

    info = {
        'bin': local_config['bins'],
        'workload': local_config['workloads'],
        'postprocessor': [join_command(post) for post in local_config['postprocessors']],
        'collector': [join_command(collect) for collect in local_config['collectors']],
        'args': local_config['args'] if 'args' in local_config.keys() else []
    }

    return info


@pass_pcs
def run_matrix_job(pcs):
    """
    Arguments:
        pcs(PCS): object with performance control system wrapper
    """
    job_matrix, number_of_jobs = construct_job_matrix(**load_job_info_from_config(pcs))
    run_jobs(pcs, job_matrix, number_of_jobs)


def run_jobs(pcs, job_matrix, number_of_jobs):
    """
    Arguments:
        pcs(PCS): object with performance control system wrapper
        job_matrix(dict): dictionary with jobs that will be run
        number_of_jobs(int): number of jobs that will be run
    """
    for job_bin, workloads_per_bin in job_matrix.items():
        print_current_phase("Collecting profiles for {}", job_bin, COLLECT_PHASE_BIN)
        for job_workload, jobs_per_workload in workloads_per_bin.items():
            print_current_phase(" - processing workload {}", job_workload, COLLECT_PHASE_WORKLOAD)
            for job in jobs_per_workload:
                print_job_progress(number_of_jobs)
                print_current_phase("Collecting data by {}", job.collector,  COLLECT_PHASE_COLLECT)

                # Run the collector and check if the profile was successfully collected
                collection_status, collection_msg, prof = runner.run_collector(job.collector, job)
                if collection_status != CollectStatus.OK:
                    perun_log.error(collection_msg)
                print("Successfully collected data from {}".format(job_bin))

                for postprocessor in job.postprocessors:
                    print_job_progress(number_of_jobs)
                    print_current_phase("Postprocessing profile with {}", postprocessor,
                                        COLLECT_PHASE_POSTPROCESS)

                    # Run the postprocessor and check if the profile was successfully postprocessed
                    post_status, post_msg, prof = runner.run_postprocessor(postprocessor, job, prof)
                    if post_status != PostprocessStatus.OK:
                        perun_log.error(post_msg)
                    print("Successfully postprocessed data by {}".format(postprocessor))

                # Store the computed profile inside the job directory
                full_profile = profile.generate_profile_for_job(prof, job)
                full_profile_name = profile.generate_profile_name(job)
                profile_directory = pcs.get_job_directory()
                full_profile_path = os.path.join(profile_directory, full_profile_name)
                profile.store_profile_at(full_profile, full_profile_path)
