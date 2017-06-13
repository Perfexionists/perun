"""Commands is a core of the perun implementation containing the basic commands.

Commands contains implementation of the basic commands of perun pcs. It is meant
to be run both from GUI applications and from CLI, where each of the function is
possible to be run in isolation.
"""

import collections
import inspect
import os
import re

import colorama
import termcolor

import perun.utils.decorators as decorators
import perun.utils.log as perun_log
import perun.utils.timestamps as timestamp
import perun.core.logic.config as perun_config
import perun.core.logic.profile as profile
import perun.core.logic.store as store
import perun.core.vcs as vcs

from perun.utils.helpers import MAXIMAL_LINE_WIDTH, \
    TEXT_EMPH_COLOUR, TEXT_ATTRS, TEXT_WARN_COLOUR, \
    PROFILE_TYPE_COLOURS, PROFILE_MALFORMED, SUPPORTED_PROFILE_TYPES, \
    HEADER_ATTRS, HEADER_COMMIT_COLOUR, HEADER_INFO_COLOUR, HEADER_SLASH_COLOUR, \
    ProfileInfo
from perun.utils.exceptions import NotPerunRepositoryException
from perun.core.logic.pcs import pass_pcs

# Init colorama for multiplatform colours
colorama.init()
UNTRACKED_REGEX = \
    re.compile(r"([^\\]+)-([0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}).perf")


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
    f_args, _, _, _, *_ = inspect.getfullargspec(func)
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
        vcs.check_minor_version_validity(pcs.vcs_type, pcs.vcs_path, args[minor_version_position])
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

    # First init the wrapping repository well
    vcs_type = kwargs['vcs_type']
    vcs_path = kwargs['vcs_path'] or dst
    vcs_params = kwargs['vcs_params']
    if vcs_type and not vcs.init(vcs_type, vcs_path, vcs_params):
        perun_log.error("Could not initialize empty {} repository at {}".format(
            vcs_type, vcs_path
        ))

    # Construct local config
    vcs_config = {
        'vcs': {
            'url': vcs_path,
            'type': vcs_type
        }
    }

    # Check if there exists perun directory above and initialize the new pcs
    try:
        super_perun_dir = store.locate_perun_dir_on(dst)
        is_pcs_reinitialized = (super_perun_dir == dst)
        if not is_pcs_reinitialized:
            perun_log.warn("There exists super perun directory at {}".format(super_perun_dir))
    except NotPerunRepositoryException:
        is_pcs_reinitialized = False

    init_perun_at(dst, kwargs['vcs_type'] == 'pvcs', is_pcs_reinitialized, vcs_config)

    # Register new performance control system in config
    global_config = perun_config.shared()
    perun_config.append_key_at_config(global_config, 'pcs', {'dir': dst})


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

    Raises:
        EntryNotFoundException: when the given profile_name points to non-tracked profile
    """
    assert minor_version is not None and "Missing minor version specification"

    perun_log.msg_to_stdout("Running inner wrapper of the 'perun rm'", 2)

    object_directory = pcs.get_object_directory()
    store.remove_from_index(object_directory, minor_version, profile_name, **kwargs)


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
    print_profile_numbers(tracked_profiles, 'tracked', ending)


def print_profile_numbers(profile_numbers, profile_type, line_ending='\n'):
    """Helper function for printing the numbers of profile to output.

    Arguments:
        profile_numbers(dict): dictionary of nomber of profiles grouped by type
        profile_type(str): type of the profiles (tracked, untracked, etc.)
        line_ending(str): ending of the print (for different outputs of log and status)
    """
    if profile_numbers['all']:
        print("{0[all]} {1} profiles (".format(profile_numbers, profile_type), end='')
        first_outputed = False
        for profile_type in SUPPORTED_PROFILE_TYPES:
            if not profile_numbers[profile_type]:
                continue
            if first_outputed:
                print(', ', end='')
            print(termcolor.colored("{0} {1}".format(
                profile_numbers[profile_type], profile_type
            ), PROFILE_TYPE_COLOURS[profile_type]), end='')
            first_outputed = True
        print(')', end=line_ending)
    else:
        print(termcolor.colored('(no {} profiles)'.format(profile_type),
                                TEXT_WARN_COLOUR, attrs=TEXT_ATTRS), end='\n')


@pass_pcs
@lookup_minor_version
def log(pcs, minor_version, short=False, **_):
    """Prints the log of the @p pcs

    Arguments:
        pcs(PCS): object with performance control system wrapper
        minor_version(str): representation of the head version
        short(bool): true if the log should be in short format
    """
    perun_log.msg_to_stdout("Running inner wrapper of the 'perun log '", 2)

    # Print header for --short-minors
    if short:
        print_short_minor_info_header()

    # Walk the minor versions and print them
    for minor in vcs.walk_minor_versions(pcs.vcs_type, pcs.vcs_path, minor_version):
        if short:
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


def print_profile_info_list(profile_list, profile_output_colour='white'):
    """
    Arguments:
        profile_list(list): list of profiles of ProfileInfo objects
        profile_output_colour(str): colour of the output profiles (red for untracked)
    """
    # Skip empty profile list
    if len(profile_list) == 0:
        return

    # Measure the maxima for the lenghts of the profile names and profile types
    maximal_profile_name_len = max(len(profile_info.path) for profile_info in profile_list)
    maximal_type_len = max(len(profile_info.type) for profile_info in profile_list)

    # Print the list of the profiles
    for profile_info in profile_list:
        print(termcolor.colored(
            "\t[{}]".format(profile_info.type).ljust(maximal_type_len+4),
            PROFILE_TYPE_COLOURS[profile_info.type], attrs=TEXT_ATTRS,
        ), end="")
        print(termcolor.colored("{0} ({1})".format(
            profile_info.path.ljust(maximal_profile_name_len),
            profile_info.time,
        ), profile_output_colour))


def print_minor_version_profiles(pcs, minor_version, short):
    """Prints profiles assigned to the given minor version.

    Arguments:
        pcs(PCS): performance control system
        minor_version(str): identification of the commit (preferably sha1)
        short(bool): whether the info about untracked profiles should be short
    """
    # Compute the
    profiles = store.get_profile_list_for_minor(pcs.get_object_directory(), minor_version)
    profile_info_list = []
    for index_entry in profiles:
        _, profile_name = store.split_object_name(pcs.get_object_directory(), index_entry.checksum)
        profile_type = store.peek_profile_type(profile_name)
        profile_info_list.append(ProfileInfo(index_entry.path, profile_type, index_entry.time))

    # Print with padding
    ending = ':\n\n' if not short else "\n"
    print_profile_number_for_minor(pcs.get_object_directory(), minor_version, ending)
    if not short:
        print_profile_info_list(profile_info_list)


def print_untracked_profiles(pcs, short):
    """Prints untracked profiles, currently residing in the .perun/jobs directory.

    Arguments:
        pcs(PCS): performance control system
        short(bool): whether the info about untracked profiles should be short
    """
    profile_numbers = collections.defaultdict(int)
    profile_list = []
    untracked = [path for path in os.listdir(pcs.get_job_directory()) if path.endswith('perf')]

    # Transform each profile of the path to the ProfileInfo object
    for untracked_path in untracked:
        real_path = os.path.join(pcs.get_job_directory(), untracked_path)
        loaded_profile = profile.load_profile_from_file(real_path, True)
        profile_type = loaded_profile['header']['type']
        path = UNTRACKED_REGEX.search(untracked_path).groups()[0]
        time = timestamp.timestamp_to_str(os.stat(real_path).st_mtime)

        # Update the list of profiles and counters of types
        profile_list.append(ProfileInfo(path, profile_type, time))
        profile_numbers[profile_type] += 1
        profile_numbers['all'] += 1

    # Output the the console
    ending = ':\n\n' if not short else "\n"
    print_profile_numbers(profile_numbers, 'untracked', ending)
    if not short:
        print_profile_info_list(profile_list, 'red')


@pass_pcs
def status(pcs, short=False):
    """Prints the status of performance control system

    Arguments:
        pcs(PCS): performance control system
        short(bool): true if the output should be short (i.e. without some information)
    """
    # Obtain both of the heads
    major_head = vcs.get_head_major_version(pcs.vcs_type, pcs.vcs_path)
    minor_head = vcs.get_minor_head(pcs.vcs_type, pcs.vcs_path)

    # Print the status of major head.
    print("On major version {} ".format(
        termcolor.colored(major_head, TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS)
    ), end='')

    # Print the index of the current head
    print("(minor version: {})".format(
        termcolor.colored(minor_head, TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS)
    ))

    # Print in long format, the additional information about head commit, by default print
    if not short:
        print("")
        minor_version = vcs.get_minor_version_info(pcs.vcs_type, pcs.vcs_path, minor_head)
        print_minor_version_info(minor_version)

    # Print profiles
    print_minor_version_profiles(pcs, minor_head, short)
    if not short:
        print("")
    print_untracked_profiles(pcs, short)


@pass_pcs
@lookup_minor_version
def load_profile_from_args(pcs, profile_name, minor_version):
    """
    Arguments:
        pcs(PCS): object with performance control system wrapper
        profile_name(Profile): profile that will be stored for the minor version
        minor_version(str): SHA-1 representation of the minor version

    Returns:
        dict: loaded profile represented as dictionary
    """
    perun_log.msg_to_stdout("Running inner wrapper of the 'perun show'", 2)

    # If the profile is in raw form
    if not store.is_sha1(profile_name):
        _, minor_index_file = store.split_object_name(pcs.get_object_directory(), minor_version)
        if not os.path.exists(minor_index_file):
            perun_log.error("index of minor version {1} has no profile '{0}' registered".format(
                profile_name, minor_version
            ))
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

    return loaded_profile
