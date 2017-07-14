"""Commands is a core of the perun implementation containing the basic commands.

Commands contains implementation of the basic commands of perun pcs. It is meant
to be run both from GUI applications and from CLI, where each of the function is
possible to be run in isolation.
"""

import collections
import inspect
import os
import re

import click
import colorama
import perun.logic.store as store
import termcolor

import perun.logic.config as perun_config
import perun.profile.factory as profile
import perun.utils as utils
import perun.utils.log as perun_log
import perun.utils.timestamps as timestamp
import perun.vcs as vcs
from perun.utils.exceptions import NotPerunRepositoryException, InvalidConfigOperationException, \
    ExternalEditorErrorException
from perun.utils.helpers import MAXIMAL_LINE_WIDTH, \
    TEXT_EMPH_COLOUR, TEXT_ATTRS, TEXT_WARN_COLOUR, \
    PROFILE_TYPE_COLOURS, PROFILE_MALFORMED, SUPPORTED_PROFILE_TYPES, \
    HEADER_ATTRS, HEADER_COMMIT_COLOUR, HEADER_INFO_COLOUR, HEADER_SLASH_COLOUR, \
    DESC_COMMIT_ATTRS, DESC_COMMIT_COLOUR, PROFILE_DELIMITER, ID_TYPE_COLOUR
from perun.utils.log import cprint, cprintln
from perun.logic.pcs import pass_pcs

# Init colorama for multiplatform colours
colorama.init()
UNTRACKED_REGEX = \
    re.compile(r"([^\\]+)-([0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}).perf")
# Regex for parsing the formating tag [<tag>:<size>f<fill_char>]
FMT_REGEX = re.compile("[[]([a-zA-Z]+)(:[0-9]+)?(f.)?[]]")
# Scanner for parsing formating strings, i.e. breaking it to parts
FMT_SCANNER = re.Scanner([
    (r"[[]([a-zA-Z]+)(:[0-9]+)?(f.)?[]]", lambda scanner, token: ("fmt_string", token)),
    (r"[^][]*", lambda scanner, token: ("rest", token)),
])


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


@pass_pcs
def config(pcs, store_type, operation, key=None, value=None, **kwargs):
    """Updates the configuration file @p config of the @p pcs perun file

    Arguments:
        pcs(PCS): object with performance control system wrapper
        store_type(str): type of the store (local, shared, or recursive)
        operation(str): type of the operation over the (key, value) pair (get, set, or edit)
        key(str): key that is looked up or stored in config
        value(str): value we are setting to config
        kwargs(dict): dictionary of keyword arguments

    Raises:
        ExternalEditorErrorException: raised if there are any problems during invoking of external
            editor during the 'edit' operation
    """
    config_store = pcs.global_config() if store_type in ('shared', 'global') else pcs.local_config()

    if operation == 'get' and key:
        if store_type == 'recursive':
            value = perun_config.lookup_key_recursively(pcs.get_config_dir('local'), key)
        else:
            value = perun_config.get_key_from_config(config_store, key)
        print("{}: {}".format(key, value))
    elif operation == 'set' and key and value:
        perun_config.set_key_at_config(config_store, key, value)
        print("Value '{1}' set for key '{0}'".format(key, value))
    # Edit operation opens the configuration in the external editor
    elif operation == 'edit':
        # Lookup the editor in the config and run it as external command
        editor = perun_config.lookup_key_recursively(pcs.path, 'global.editor')
        config_file = pcs.get_config_file(store_type)
        try:
            utils.run_external_command([editor, config_file])
        except Exception as inner_exception:
            raise ExternalEditorErrorException(editor, str(inner_exception))
    else:
        raise InvalidConfigOperationException(store_type, operation, key, value)


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


@pass_pcs
@lookup_minor_version
def add(pcs, profile_name, minor_version, keep_profile=False):
    """Appends @p profile to the @p minor_version inside the @p pcs

    Arguments:
        pcs(PCS): object with performance control system wrapper
        profile_name(Profile): profile that will be stored for the minor version
        minor_version(str): SHA-1 representation of the minor version
        keep_profile(bool): if true, then the profile that is about to be added will be not
            deleted, and will be kept as it is. By default false, i.e. profile is deleted.
    """
    assert minor_version is not None and "Missing minor version specification"

    perun_log.msg_to_stdout("Running inner wrapper of the 'perun add' with args {}, {}, {}".format(
        pcs, profile_name, minor_version
    ), 2)

    # Test if the given profile exists
    if not os.path.exists(profile_name):
        perun_log.error("{} does not exists".format(profile_name))

    # Load profile content
    # Unpack to JSON representation
    unpacked_profile = profile.load_profile_from_file(profile_name, True)
    assert 'type' in unpacked_profile['header'].keys()

    if unpacked_profile['origin'] != minor_version:
        perun_log.error("cannot add profile '{}' to minor index of '{}':"
                        "profile originates from minor version '{]'"
                        "".format(profile_name, minor_version, unpacked_profile['origin']))

    # Remove origin from file
    unpacked_profile.pop('origin')
    profile_content = profile.to_string(unpacked_profile)

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

    # Remove the file
    if not keep_profile:
        os.remove(profile_name)


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
    slash = termcolor.colored(PROFILE_DELIMITER, HEADER_SLASH_COLOUR, attrs=HEADER_ATTRS)
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


def calculate_profile_numbers_per_type(profile_list):
    """Calculates how many profiles of given type are in the profile type.

    Returns dictionary mapping types of profiles (i.e. memory, time, ...) to the
    number of profiles that are occurring in the profile list. Used for statistics
    about profiles corresponding to minor versions.

    Arguments:
        profile_list(list): list of ProfileInfo with information about profiles

    Returns:
        dict: dictionary mapping profile types to number of profiles of given type in the list
    """
    profile_numbers = collections.defaultdict(int)
    for profile_info in profile_list:
        profile_numbers[profile_info.type] += 1
    profile_numbers['all'] = len(profile_list)
    return profile_numbers


def print_profile_numbers(profile_numbers, profile_types, line_ending='\n'):
    """Helper function for printing the numbers of profile to output.

    Arguments:
        profile_numbers(dict): dictionary of number of profiles grouped by type
        profile_types(str): type of the profiles (tracked, untracked, etc.)
        line_ending(str): ending of the print (for different outputs of log and status)
    """
    if profile_numbers['all']:
        print("{0[all]} {1} profiles (".format(profile_numbers, profile_types), end='')
        first_printed = False
        for profile_type in SUPPORTED_PROFILE_TYPES:
            if not profile_numbers[profile_type]:
                continue
            print(', ' if first_printed else '', end='')
            first_printed = True
            type_colour = PROFILE_TYPE_COLOURS[profile_type]
            cprint("{0} {1}".format(profile_numbers[profile_type], profile_type), type_colour)
        print(')', end=line_ending)
    else:
        cprintln('(no {} profiles)'.format(profile_types), TEXT_WARN_COLOUR, attrs=TEXT_ATTRS)


@pass_pcs
@lookup_minor_version
def log(pcs, minor_version, short=False, **_):
    """Prints the log of the performance control system

    Either prints the short or longer version. In short version, only header and short
    list according to the formatting string from stored in the configuration. Prints
    the number of profiles associated with each of the minor version and some basic
    information about minor versions, like e.g. description, hash, etc.

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
            cprintln("Minor Version {}".format(minor.checksum), TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS)
            base_dir = pcs.get_object_directory()
            tracked_profiles = store.get_profile_number_for_minor(base_dir, minor.checksum)
            print_profile_numbers(tracked_profiles, 'tracked')
            print_minor_version_info(minor, indent=1)


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
                termcolor.colored(PROFILE_DELIMITER, HEADER_SLASH_COLOUR),
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
    print(termcolor.colored(
        " {0} ".format(short_description), DESC_COMMIT_COLOUR, attrs=DESC_COMMIT_ATTRS
    ))


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


def print_formating_token(fmt_string, info_object, info_attr, size_limit,
                          default_color='white', value_fill=' '):
    """Prints the token from the fmt_string, according to the values stored in info_object

    info_attr is one of the tokens from fmt_string, which is extracted from the info_object,
    that stores the real value. This value is then outputed to stdout with colours, fills,
    and is trimmed to the given size.

    Arguments:
        fmt_string(str): formating string for the given token
        info_object(object): object with stored information (ProfileInfo or MinorVersion)
        size_limit(int): will limit the output of the value of the info_object to this size
        info_attr(str): attribute we are looking up in the info_object
        default_color(str): default colour of the formatting token that will be printed out
        value_fill(char): will fill the string with this
    """
    # Check if encountered incorrect token in the formating string
    if not hasattr(info_object, info_attr):
        perun_log.error("invalid formating string '{}'".format(fmt_string))

    # Obtain the value for the printing
    profile_raw_value = getattr(info_object, info_attr)
    profile_info_value = profile_raw_value.ljust(size_limit, value_fill)

    # Print the actual token
    if info_attr == 'type':
        cprint("[{}]".format(profile_info_value), PROFILE_TYPE_COLOURS[profile_raw_value])
    elif info_attr == 'id':
        cprint("{}".format(profile_info_value), ID_TYPE_COLOUR)
    else:
        cprint(profile_info_value, default_color)


def calculate_maximal_lenghts_for_profile_infos(profile_list):
    """For given profile list, will calculate the maximal sizes for its values for table view.

    Arguments:
        profile_list(list): list of ProfileInfo informations

    Returns:
        dict: dictionary with maximal lengths for profiles
    """
    # Measure the maxima for the lenghts of the profile names and profile types
    max_lengths = collections.defaultdict(int)
    for profile_info in profile_list:
        for attr in profile.ProfileInfo.valid_attributes:
            assert hasattr(profile_info, attr)
            max_lengths[attr] \
                = max(len(attr), max_lengths[attr], len(str(getattr(profile_info, attr))))
    return max_lengths


def print_profile_info_list(pcs, profile_list, max_lengths, short, list_type='tracked'):
    """Prints list of profiles and counts per type of tracked/untracked profiles.

    Prints the list of profiles, trims the sizes of each information according to the
    computed maximal lengths If the output is short, the list itself is not printed,
    just the information about counts. Tracked and untracked differs in colours.

    Arguments:
        pcs(PCS): wrapped perun repository
        profile_list(list): list of profiles of ProfileInfo objects
        max_lengths(dict): dictionary with maximal sizes for the output of profiles
        short(bool): true if the output should be short
        list_type(str): type of the profile list (either untracked or tracked)
    """
    # Print with padding
    profile_output_colour = 'white' if list_type == 'tracked' else 'red'
    index_id_char = 'i' if list_type == 'tracked' else 'p'
    ending = ':\n\n' if not short else "\n"

    profile_numbers = calculate_profile_numbers_per_type(profile_list)
    print_profile_numbers(profile_numbers, list_type, ending)

    # Skip empty profile list
    profile_list_len = len(profile_list)
    profile_list_width = len(str(profile_list_len))
    if not profile_list_len or short:
        return

    # Load formating string for profile
    profile_info_fmt = perun_config.lookup_key_recursively(pcs.path, 'global.profile_info_fmt')
    fmt_tokens, _ = FMT_SCANNER.scan(profile_info_fmt)

    # Compute header length
    header_len = profile_list_width + 3
    for (token_type, token) in fmt_tokens:
        if token_type == 'fmt_string':
            attr_type, limit, _ = FMT_REGEX.match(token).groups()
            limit = limit or max_lengths[attr_type] + (2 if attr_type == 'type' else 0)
            header_len += limit
        else:
            header_len += len(token)

    cprintln("\u2550"*header_len + "\u25A3", profile_output_colour)
    # Print header (2 is padding for id)
    print(" ", end='')
    cprint("id".center(profile_list_width + 2, ' '), profile_output_colour)
    print(" ", end='')
    for (token_type, token) in fmt_tokens:
        if token_type == 'fmt_string':
            attr_type, limit, _ = FMT_REGEX.match(token).groups()
            limit = limit or max_lengths[attr_type] + (2 if attr_type == 'type' else 0)
            token_string = attr_type.center(limit, ' ')
            cprint(token_string, profile_output_colour, [])
        else:
            # Print the rest (non token stuff)
            cprint(token, profile_output_colour)
    print("")
    cprintln("\u2550"*header_len + "\u25A3", profile_output_colour)
    # Print profiles
    for profile_no, profile_info in enumerate(profile_list):
        print(" ", end='')
        cprint("{}@{}".format(profile_no, index_id_char).rjust(profile_list_width + 2, ' '),
               profile_output_colour)
        print(" ", end='')
        for (token_type, token) in fmt_tokens:
            if token_type == 'fmt_string':
                attr_type, limit, fill = FMT_REGEX.match(token).groups()
                limit = limit or max_lengths[attr_type]
                print_formating_token(profile_info_fmt, profile_info, attr_type, limit,
                                      default_color=profile_output_colour, value_fill=fill or ' ')
            else:
                cprint(token, profile_output_colour)
        print("")
    cprintln("\u2550"*header_len + "\u25A3", profile_output_colour)


@pass_pcs
@lookup_minor_version
def get_nth_profile_of(pcs, position, minor_version):
    """Returns the profile at nth position in the index

    Arguments:
        pcs(PCS): wrapped perun control system
        position(int): position of the profile we are obtaining
        minor_version(str): looked up minor version for the wrapped vcs
    """
    registered_profiles = get_minor_version_profiles(pcs, minor_version)
    if 0 <= position < len(registered_profiles):
        return registered_profiles[position].id
    else:
        raise click.BadParameter("invalid tag '{}' (choose from interval <{}, {}>)".format(
            "{}@i".format(position), "0@i", "{}@i".format(len(registered_profiles)-1)
        ))


def get_minor_version_profiles(pcs, minor_version):
    """Returns profiles assigned to the given minor version.

    Arguments:
        pcs(PCS): performance control system
        minor_version(str): identification of the commit (preferably sha1)

    Returns:
        list: list of ProfileInfo parsed from index of the given minor_version
    """
    # Compute the
    profiles = store.get_profile_list_for_minor(pcs.get_object_directory(), minor_version)
    profile_info_list = []
    for index_entry in profiles:
        _, profile_name = store.split_object_name(pcs.get_object_directory(), index_entry.checksum)
        profile_info \
            = profile.ProfileInfo(index_entry.path, profile_name, index_entry.time)
        profile_info_list.append(profile_info)

    return profile_info_list


def get_untracked_profiles(pcs):
    """Returns list untracked profiles, currently residing in the .perun/jobs directory.

    Arguments:
        pcs(PCS): performance control system

    Returns:
        list: list of ProfileInfo parsed from .perun/jobs directory
    """
    profile_list = []
    # Transform each profile of the path to the ProfileInfo object
    for untracked_path in os.listdir(pcs.get_job_directory()):
        if not untracked_path.endswith('perf'):
            continue

        real_path = os.path.join(pcs.get_job_directory(), untracked_path)
        time = timestamp.timestamp_to_str(os.stat(real_path).st_mtime)

        # Update the list of profiles and counters of types
        profile_info = profile.ProfileInfo(untracked_path, real_path, time, is_raw_profile=True)
        profile_list.append(profile_info)

    return profile_list


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
    minor_version_profiles = get_minor_version_profiles(pcs, minor_head)
    untracked_profiles = get_untracked_profiles(pcs)
    maxs = calculate_maximal_lenghts_for_profile_infos(minor_version_profiles + untracked_profiles)
    print_profile_info_list(pcs, minor_version_profiles, maxs, short)
    if not short:
        print("")
    print_profile_info_list(pcs, untracked_profiles, maxs, short, 'untracked')


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
        return None
    chosen_profile = profiles[0]

    # Peek the type if the profile is correct and load the json
    _, profile_name = store.split_object_name(pcs.get_object_directory(), chosen_profile.checksum)
    profile_type = store.peek_profile_type(profile_name)
    if profile_type == PROFILE_MALFORMED:
        perun_log.error("malformed profile {}".format(profile_name))
    loaded_profile = profile.load_profile_from_file(profile_name, False)

    return loaded_profile
