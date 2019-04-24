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
import termcolor
from operator import itemgetter

import perun.logic.pcs as pcs
import perun.logic.config as perun_config
import perun.logic.store as store
import perun.logic.index as index
import perun.profile.factory as profile
import perun.utils as utils
import perun.utils.log as perun_log
import perun.utils.timestamps as timestamp
import perun.vcs as vcs
import perun.logic.temp as temp

from perun.utils.exceptions import NotPerunRepositoryException, \
    ExternalEditorErrorException, MissingConfigSectionException, InvalidTempPathException, \
    ProtectedTempException
from perun.utils.helpers import \
    TEXT_EMPH_COLOUR, TEXT_ATTRS, TEXT_WARN_COLOUR, \
    PROFILE_TYPE_COLOURS, SUPPORTED_PROFILE_TYPES, HEADER_ATTRS, HEADER_COMMIT_COLOUR, \
    HEADER_INFO_COLOUR, HEADER_SLASH_COLOUR, PROFILE_DELIMITER, MinorVersion
from perun.utils.log import cprint, cprintln

# Init colorama for multiplatform colours
colorama.init()
UNTRACKED_REGEX = \
    re.compile(r"([^\\]+)-([0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}).perf")
# Regex for parsing the formating tag [<tag>:<size>f<fill_char>]
FMT_REGEX = re.compile("%([a-zA-Z]+)(:[0-9]+)?(f.)?%")
# Scanner for parsing formating strings, i.e. breaking it to parts
FMT_SCANNER = re.Scanner([
    (r"%([a-zA-Z]+)(:[0-9]+)?(f.)?%", lambda scanner, token: ("fmt_string", token)),
    (r"[^%]+", lambda scanner, token: ("rest", token)),
])


def lookup_minor_version(func):
    """If the minor_version is not given by the caller, it looks up the HEAD in the repo.

    If the @p func is called with minor_version parameter set to None,
    then this decorator performs a lookup of the minor_version corresponding
    to the head of the repository.

    :param function func: decorated function for which we will lookup the minor_version
    :returns function: decorated function, with minor_version translated or obtained
    """
    f_args, _, _, _, *_ = inspect.getfullargspec(func)
    minor_version_position = f_args.index('minor_version')

    def wrapper(*args, **kwargs):
        """Inner wrapper of the function"""
        # if the minor_version is None, then we obtain the minor head for the wrapped type
        if minor_version_position < len(args) and args[minor_version_position] is None:
            # note: since tuples are immutable we have to do this workaround
            arg_list = list(args)
            arg_list[minor_version_position] = vcs.get_minor_head()
            args = tuple(arg_list)
        else:
            vcs.check_minor_version_validity(args[minor_version_position])
        return func(*args, **kwargs)

    return wrapper


def config_get(store_type, key):
    """Gets from the store_type configuration the value of the given key.

    :param str store_type: type of the store lookup (local, shared of recursive)
    :param str key: list of section delimited by dot (.)
    """
    config_store = pcs.global_config() if store_type in ('shared', 'global') else pcs.local_config()

    if store_type == 'recursive':
        value = perun_config.lookup_key_recursively(key)
    else:
        value = config_store.get(key)
    print("{}: {}".format(key, value))


def config_set(store_type, key, value):
    """Sets in the store_type configuration the key to the given value.

    :param str store_type: type of the store lookup (local, shared of recursive)
    :param str key: list of section delimited by dot (.)
    :param object value: arbitrary value that will be set in the configuration
    """
    config_store = pcs.global_config() if store_type in ('shared', 'global') else pcs.local_config()

    config_store.set(key, value)
    print("Value '{1}' set for key '{0}'".format(key, value))


def config_edit(store_type):
    """Runs the external editor stored in general.editor key in order to edit the config file.

    :param str store_type: type of the store (local, shared, or recursive)
    :raises MissingConfigSectionException: when the general.editor is not found in any config
    :raises ExternalEditorErrorException: raised if there are any problems during invoking of
        external editor during the 'edit' operation
    """
    # Lookup the editor in the config and run it as external command
    editor = perun_config.lookup_key_recursively('general.editor')
    config_file = pcs.get_config_file(store_type)
    try:
        utils.run_external_command([editor, config_file])
    except Exception as inner_exception:
        raise ExternalEditorErrorException(editor, str(inner_exception))


def config_reset(store_type, config_template):
    """Resets the given store_type to a default type (or to a selected configuration template)

    For more information about configuration templates see :ref:`config-templates`.

    :param str store_type: name of the store (local or global) which we are resetting
    :param str config_template: name of the template that we are resetting to
    :raises NotPerunRepositoryException: raised when we are outside of any perun scope
    """
    if store_type in ('shared', 'global'):
        shared_location = perun_config.lookup_shared_config_dir()
        perun_config.init_shared_config_at(shared_location)
    else:
        vcs_config = {
            'vcs': {
                'url': pcs.get_vcs_path(),
                'type': pcs.get_vcs_type()
            }
        }
        perun_config.init_local_config_at(pcs.get_path(), vcs_config, config_template)
    perun_log.info("{} configuration reset{}".format(
        'global' if store_type in ('shared', 'global') else 'local',
        " to {}".format(config_template) if store not in ("shared", "global") else ""
    ))


def init_perun_at(perun_path, is_reinit, vcs_config, config_template='master'):
    """Initialize the .perun directory at given path

    Initializes or reinitializes the .perun directory at the given path.

    :param path perun_path: path where new perun performance control system will be stored
    :param bool is_reinit: true if this is existing perun, that will be reinitialized
    :param dict vcs_config: dictionary of form {'vcs': {'type', 'url'}} for local config init
    :param str config_template: name of the configuration template
    """
    # Initialize the basic structure of the .perun directory
    perun_full_path = os.path.join(perun_path, '.perun')
    store.touch_dir(perun_full_path)
    store.touch_dir(os.path.join(perun_full_path, 'objects'))
    store.touch_dir(os.path.join(perun_full_path, 'jobs'))
    store.touch_dir(os.path.join(perun_full_path, 'logs'))
    store.touch_dir(os.path.join(perun_full_path, 'cache'))
    store.touch_dir(os.path.join(perun_full_path, 'stats'))
    store.touch_dir(os.path.join(perun_full_path, 'tmp'))
    # If the config does not exist, we initialize the new version
    if not os.path.exists(os.path.join(perun_full_path, 'local.yml')):
        perun_config.init_local_config_at(perun_full_path, vcs_config, config_template)
    else:
        perun_log.info('configuration file already exists. Run ``perun config reset`` to reset'
                       ' configuration to default state.')

    # Perun successfully created
    msg_prefix = "Reinitialized existing" if is_reinit else "Initialized empty"
    perun_log.msg_to_stdout(msg_prefix + " Perun repository in {}".format(perun_path), 0)


def init(dst, configuration_template='master', **kwargs):
    """Initializes the performance and version control systems

    Inits the performance control system at a given directory. Optionally inits the
    wrapper of the Version Control System that is used as tracking point.

    :param path dst: path where the pcs will be initialized
    :param dict kwargs: keyword arguments of the initialization
    :param str configuration_template: name of the template that will be used for initialization
        of local configuration
    """
    perun_log.msg_to_stdout("call init({}, {})".format(dst, kwargs), 2)

    # First init the wrapping repository well
    vcs_type = kwargs['vcs_type']
    vcs_path = kwargs['vcs_path'] or dst
    vcs_params = kwargs['vcs_params']

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

    init_perun_at(dst, is_pcs_reinitialized, vcs_config, configuration_template)

    # If the wrapped repo could not be initialized we end with error. The user should adjust this
    # himself and fix it in the config. Note that this decision was made after tagit design,
    # where one needs to further adjust some options in initialized directory.
    if vcs_type and not vcs.init(vcs_params):
        err_msg = "Could not initialize empty {0} repository at {1}.\n".format(vcs_type, vcs_path)
        err_msg += "Either reinitialize perun with 'perun init' or initialize {0} repository"
        err_msg += "manually and fix the path to vcs in 'perun config --edit'"
        perun_log.error(err_msg)


@lookup_minor_version
def add(profile_names, minor_version, keep_profile=False, force=False):
    """Appends @p profile to the @p minor_version inside the @p pcs

    :param generator profile_names: generator of profiles that will be stored for the minor version
    :param str minor_version: SHA-1 representation of the minor version
    :param bool keep_profile: if true, then the profile that is about to be added will be not
        deleted, and will be kept as it is. By default false, i.e. profile is deleted.
    :param bool force: if set to true, then the add will be forced, i.e. the check for origin will
        not be performed.
    """
    added_profile_count = 0
    for profile_name in profile_names:
        # Test if the given profile exists (This should hold always, or not?)
        if not os.path.exists(profile_name):
            perun_log.error("profile {} does not exists".format(profile_name), recoverable=True)
            continue

        # Load profile content
        # Unpack to JSON representation
        unpacked_profile = store.load_profile_from_file(profile_name, True)

        if not force and unpacked_profile['origin'] != minor_version:
            error_msg = "cannot add profile '{}' to minor index of '{}':".format(
                profile_name, minor_version
            )
            error_msg += "profile originates from minor version '{}'".format(
                unpacked_profile['origin']
            )
            perun_log.error(error_msg, recoverable=True)
            continue

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
        object_dir = pcs.get_object_directory()
        store.add_loose_object_to_dir(object_dir, profile_sum, compressed_content)

        # Register in the minor_version index
        index.register_in_minor_index(
            object_dir, minor_version, profile_name, profile_sum, unpacked_profile
        )

        # Remove the file
        if not keep_profile:
            os.remove(profile_name)

        added_profile_count += 1

    profile_names_len = len(profile_names)
    if added_profile_count != profile_names_len:
        perun_log.error("could not register {}{} profile{} in index: {} failed".format(
            "all " if added_profile_count > 1 else "",
            added_profile_count, "s" if added_profile_count > 1 else "",
            added_profile_count - profile_names_len
        ))
    perun_log.info("successfully registered {} profiles in index".format(added_profile_count))


@lookup_minor_version
def remove(profile_generator, minor_version, **kwargs):
    """Removes @p profile from the @p minor_version inside the @p pcs

    :param generator profile_generator: profile that will be stored for the minor version
    :param str minor_version: SHA-1 representation of the minor version
    :param dict kwargs: dictionary with additional options
    :raisesEntryNotFoundException: when the given profile_generator points to non-tracked profile
    """
    perun_log.msg_to_stdout("Running inner wrapper of the 'perun rm'", 2)

    object_directory = pcs.get_object_directory()
    index.remove_from_index(object_directory, minor_version, profile_generator, **kwargs)
    perun_log.info("successfully removed {} from index".format(len(profile_generator)))


def calculate_profile_numbers_per_type(profile_list):
    """Calculates how many profiles of given type are in the profile type.

    Returns dictionary mapping types of profiles (i.e. memory, time, ...) to the
    number of profiles that are occurring in the profile list. Used for statistics
    about profiles corresponding to minor versions.

    :param list profile_list: list of ProfileInfo with information about profiles
    :returns dict: dictionary mapping profile types to number of profiles of given type in the list
    """
    profile_numbers = collections.defaultdict(int)
    for profile_info in profile_list:
        profile_numbers[profile_info.type] += 1
    profile_numbers['all'] = len(profile_list)
    return profile_numbers


def print_profile_numbers(profile_numbers, profile_types, line_ending='\n'):
    """Helper function for printing the numbers of profile to output.

    :param dict profile_numbers: dictionary of number of profiles grouped by type
    :param str profile_types: type of the profiles (tracked, untracked, etc.)
    :param str line_ending: ending of the print (for different outputs of log and status)
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


def turn_off_paging_wrt_config(paged_function):
    """Helper function for checking if the function should be paged or not according to the config
    setting ``general.paging``.

    If in global config the ``genera.paging`` is set to ``always``, then any function should be
    paged. Otherwise we check if ``general.paging`` contains either ``only-log`` or ``only-status``.

    :param str paged_function: name of the paged function, which will be looked up in config
    :return: true if the function should be paged (unless --no-pager is set)
    """
    try:
        paging_option = perun_config.shared().get('general.paging')
    # Test for backward compatibility with old instances of Perun and possible issues
    except MissingConfigSectionException:
        perun_log.warn("""corrupted shared configuration file: missing ``general.paging`` option.

Run ``perun config --shared --edit`` and set the ``general.paging`` to one of following:
    always, only-log, only-status, never

Consult the documentation (Configuration and Logs) for more information about paging of
output of status, log and others.
        """)
        return True
    return paging_option == 'always' or \
        (paging_option.startswith('only-') and paging_option.endswith(paged_function))


@perun_log.paged_function(paging_switch=turn_off_paging_wrt_config('log'))
@lookup_minor_version
def log(minor_version, short=False, **_):
    """Prints the log of the performance control system

    Either prints the short or longer version. In short version, only header and short
    list according to the formatting string from stored in the configuration. Prints
    the number of profiles associated with each of the minor version and some basic
    information about minor versions, like e.g. description, hash, etc.

    :param str minor_version: representation of the head version
    :param bool short: true if the log should be in short format
    """
    perun_log.msg_to_stdout("Running inner wrapper of the 'perun log '", 2)

    # Print header for --short-minors
    if short:
        minor_versions = list(vcs.walk_minor_versions(minor_version))
        # Reduce the descriptions of minor version to one liners
        for mv_no, minor in enumerate(minor_versions):
            minor_versions[mv_no] = minor._replace(desc=minor.desc.split("\n")[0])
        minor_version_maxima = calculate_maximal_lengths_for_object_list(
            minor_versions, MinorVersion._fields
        )
        # Update manually the maxima for the printed supported profile types, each requires two
        # characters and 9 stands for " profiles" string

        def minor_stat_retriever(minor_v):
            """Helper function for picking stats of the given minor version

            :param MinorVersion minor_v: minor version for which we are retrieving the stats
            :return: dictionary with stats for minor version
            """
            return index.get_profile_number_for_minor(
                pcs.get_object_directory(), minor_v.checksum
            )

        def deg_count_retriever(minor_v):
            """Helper function for picking stats of the degradation strings of form ++--

            :param MinorVersion minor_v: minor version for which we are retrieving the stats
            :return: dictionary with stats for minor version
            """
            counts = perun_log.count_degradations_per_group(
                store.load_degradation_list_for(pcs.get_object_directory(), minor_v.checksum)
            )
            return {'changes': counts.get('Optimization', 0)*'+' + counts.get('Degradation', 0)*'-'}

        minor_version_maxima.update(
            calculate_maximal_lengths_for_stats(minor_versions, minor_stat_retriever)
        )
        minor_version_maxima.update(
            calculate_maximal_lengths_for_stats(minor_versions, deg_count_retriever, " changes ")
        )
        print_short_minor_version_info_list(minor_versions, minor_version_maxima)
    else:
        # Walk the minor versions and print them
        for minor in vcs.walk_minor_versions(minor_version):
            cprintln("Minor Version {}".format(minor.checksum), TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS)
            base_dir = pcs.get_object_directory()
            tracked_profiles = index.get_profile_number_for_minor(base_dir, minor.checksum)
            print_profile_numbers(tracked_profiles, 'tracked')
            print_minor_version_info(minor, indent=1)


def adjust_limit(limit, attr_type, maxima, padding=0):
    """Returns the adjusted value of the limit for the given field output in status or log

    Takes into the account the limit, which is specified in the field (e.g. as checksum:6),
    the maximal values of the given fields. Additionally, one can add a padding, e.g. for
    the type tag.

    :param match limit: matched string from the formatting string specifying the limit
    :param str attr_type: string name of the attribute, which we are limiting
    :param dict maxima: maximas of values of given attribute types
    :param int padding: additional padding of the limit not contributed to maxima
    :return: adjusted value of the limit w.r.t. attribute type and maxima
    """
    return max(int(limit[1:]), len(attr_type)) if limit else maxima[attr_type] + padding


def print_short_minor_version_info_list(minor_version_list, max_lengths):
    """Prints list of profiles and counts per type of tracked/untracked profiles.

    Prints the list of profiles, trims the sizes of each information according to the
    computed maximal lengths If the output is short, the list itself is not printed,
    just the information about counts. Tracked and untracked differs in colours.

    :param list minor_version_list: list of profiles of MinorVersionInfo objects
    :param dict max_lengths: dictionary with maximal sizes for the output of profiles
    """
    # Load formating string for profile
    stat_length = sum([
        max_lengths['all'], max_lengths['time'], max_lengths['mixed'], max_lengths['memory']
    ]) + 3 + len(" profiles")
    minor_version_output_colour = 'white'
    minor_version_info_fmt = perun_config.lookup_key_recursively('format.shortlog')
    fmt_tokens, _ = FMT_SCANNER.scan(minor_version_info_fmt)
    slash = termcolor.colored(PROFILE_DELIMITER, HEADER_SLASH_COLOUR, attrs=HEADER_ATTRS)

    # Print header (2 is padding for id)
    for (token_type, token) in fmt_tokens:
        if token_type == 'fmt_string':
            attr_type, limit, _ = FMT_REGEX.match(token).groups()
            if attr_type == 'stats':
                end_msg = termcolor.colored(' profiles', HEADER_SLASH_COLOUR, attrs=HEADER_ATTRS)
                print(termcolor.colored("{0}{4}{1}{4}{2}{4}{3}{5}".format(
                    termcolor.colored(
                        'a'.rjust(max_lengths['all']), HEADER_COMMIT_COLOUR, attrs=HEADER_ATTRS
                    ),
                    termcolor.colored(
                        'm'.rjust(max_lengths['memory']),
                        PROFILE_TYPE_COLOURS['memory'], attrs=HEADER_ATTRS
                    ),
                    termcolor.colored(
                        'x'.rjust(max_lengths['mixed']),
                        PROFILE_TYPE_COLOURS['mixed'], attrs=HEADER_ATTRS),
                    termcolor.colored(
                        't'.rjust(max_lengths['time']),
                        PROFILE_TYPE_COLOURS['time'], attrs=HEADER_ATTRS),
                    slash,
                    end_msg
                ), HEADER_SLASH_COLOUR, attrs=HEADER_ATTRS), end='')
            else:
                limit = adjust_limit(limit, attr_type, max_lengths)
                token_string = attr_type.center(limit, ' ')
                cprint(token_string, minor_version_output_colour, attrs=HEADER_ATTRS)
        else:
            # Print the rest (non token stuff)
            cprint(token, minor_version_output_colour, attrs=HEADER_ATTRS)
    print("")
    # Print profiles
    for minor_version in minor_version_list:
        for (token_type, token) in fmt_tokens:
            if token_type == 'fmt_string':
                attr_type, limit, fill = FMT_REGEX.match(token).groups()
                limit = max(int(limit[1:]), len(attr_type)) if limit else max_lengths[attr_type]
                if attr_type == 'stats':
                    tracked_profiles = index.get_profile_number_for_minor(
                        pcs.get_object_directory(), minor_version.checksum
                    )
                    if tracked_profiles['all']:
                        print(termcolor.colored("{:{}}".format(
                            tracked_profiles['all'], max_lengths['all']
                        ), TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS), end='')

                        # Print the coloured numbers
                        for profile_type in SUPPORTED_PROFILE_TYPES:
                            print("{}{}".format(
                                termcolor.colored(PROFILE_DELIMITER, HEADER_SLASH_COLOUR),
                                termcolor.colored("{:{}}".format(
                                    tracked_profiles[profile_type], max_lengths[profile_type]
                                ), PROFILE_TYPE_COLOURS[profile_type])
                            ), end='')

                        print(
                            termcolor.colored(
                                " profiles", HEADER_INFO_COLOUR, attrs=TEXT_ATTRS
                            ), end=''
                        )
                    else:
                        print(
                            termcolor.colored(
                                '--no--profiles--'.center(stat_length), TEXT_WARN_COLOUR,
                                attrs=TEXT_ATTRS
                            ), end=''
                        )
                elif attr_type == 'changes':
                    degradations = store.load_degradation_list_for(
                        pcs.get_object_directory(), minor_version.checksum
                    )
                    change_string = perun_log.change_counts_to_string(
                        perun_log.count_degradations_per_group(degradations),
                        width=max_lengths['changes']
                    )
                    print(change_string, end='')
                else:
                    print_formating_token(
                        minor_version_info_fmt, minor_version, attr_type, limit,
                        default_color=minor_version_output_colour, value_fill=fill or ' '
                    )
            else:
                cprint(token, minor_version_output_colour)
        print("")


def print_minor_version_info(head_minor_version, indent=0):
    """
    :param MinorVersion head_minor_version: identification of the commit (preferably sha1)
    :param int indent: indent of the description part
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
    that stores the real value. This value is then output to stdout with colours, fills,
    and is trimmed to the given size.

    :param str fmt_string: formatting string for the given token
    :param object info_object: object with stored information (ProfileInfo or MinorVersion)
    :param int size_limit: will limit the output of the value of the info_object to this size
    :param str info_attr: attribute we are looking up in the info_object
    :param str default_color: default colour of the formatting token that will be printed out
    :param char value_fill: will fill the string with this
    """
    # Check if encountered incorrect token in the formating string
    if not hasattr(info_object, info_attr):
        perun_log.error("invalid formatting string '{}': "
                        "object does not contain '{}' attribute".format(
                            fmt_string, info_attr))

    # Obtain the value for the printing
    raw_value = getattr(info_object, info_attr)
    info_value = raw_value[:size_limit].ljust(size_limit, value_fill)

    # Print the actual token
    if info_attr == 'type':
        cprint("[{}]".format(info_value), PROFILE_TYPE_COLOURS[raw_value])
    else:
        cprint(info_value, default_color)


def calculate_maximal_lengths_for_stats(obj_list, stat_function, stat_header=""):
    """For given object lists and stat_function compute maximal lengths of the stats

    :param list obj_list: list of object, for which the stat function will be applied
    :param function stat_function: function returning the dictionary of keys
    :param str stat_header: header of the stats
    :return: dictionary of maximal lenghts for various stats
    """
    maxima = collections.defaultdict(int)
    for obj in obj_list:
        object_stats = stat_function(obj)
        for key in object_stats.keys():
            maxima[key] = max(len(stat_header), maxima[key], len(str(object_stats[key])))
    return maxima


def calculate_maximal_lengths_for_object_list(object_list, valid_attributes):
    """For given object list, will calculate the maximal sizes for its values for table view.

    :param list object_list: list of objects (e.g. ProfileInfo or MinorVersion) information
    :param list valid_attributes: list of valid attributes of objects from list
    :returns dict: dictionary with maximal lengths for profiles
    """
    # Measure the maxima for the lengths of the object info
    max_lengths = collections.defaultdict(int)
    for object_info in object_list:
        for attr in valid_attributes:
            if hasattr(object_info, attr):
                max_lengths[attr] \
                    = max(len(attr), max_lengths[attr], len(str(getattr(object_info, attr))))
    return max_lengths


def print_profile_info_list(profile_list, max_lengths, short, list_type='tracked'):
    """Prints list of profiles and counts per type of tracked/untracked profiles.

    Prints the list of profiles, trims the sizes of each information according to the
    computed maximal lengths If the output is short, the list itself is not printed,
    just the information about counts. Tracked and untracked differs in colours.

    :param list profile_list: list of profiles of ProfileInfo objects
    :param dict max_lengths: dictionary with maximal sizes for the output of profiles
    :param bool short: true if the output should be short
    :param str list_type: type of the profile list (either untracked or tracked)
    """
    # Sort the profiles w.r.t time of creation
    profile.sort_profiles(profile_list)

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
    profile_info_fmt = perun_config.lookup_key_recursively('format.status')
    fmt_tokens, _ = FMT_SCANNER.scan(profile_info_fmt)

    # Compute header length
    header_len = profile_list_width + 3
    for (token_type, token) in fmt_tokens:
        if token_type == 'fmt_string':
            attr_type, limit, _ = FMT_REGEX.match(token).groups()
            limit = adjust_limit(limit, attr_type, max_lengths, (2 if attr_type == 'type' else 0))
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
            limit = adjust_limit(limit, attr_type, max_lengths, (2 if attr_type == 'type' else 0))
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
                limit = adjust_limit(limit, attr_type, max_lengths)
                print_formating_token(profile_info_fmt, profile_info, attr_type, limit,
                                      default_color=profile_output_colour, value_fill=fill or ' ')
            else:
                cprint(token, profile_output_colour)
        print("")
        if profile_no % 5 == 0 or profile_no == profile_list_len - 1:
            cprintln("\u2550"*header_len + "\u25A3", profile_output_colour)


@lookup_minor_version
def get_nth_profile_of(position, minor_version):
    """Returns the profile at nth position in the index

    :param int position: position of the profile we are obtaining
    :param str minor_version: looked up minor version for the wrapped vcs
    """
    registered_profiles = profile.load_list_for_minor_version(minor_version)
    profile.sort_profiles(registered_profiles)
    if 0 <= position < len(registered_profiles):
        return registered_profiles[position].realpath
    else:
        raise click.BadParameter("invalid tag '{}' (choose from interval <{}, {}>)".format(
            "{}@i".format(position), "0@i", "{}@i".format(len(registered_profiles)-1)
        ))


def get_untracked_profiles():
    """Returns list untracked profiles, currently residing in the .perun/jobs directory.

    :returns list: list of ProfileInfo parsed from .perun/jobs directory
    """
    saved_entries = []
    profile_list = []
    # First load untracked files from the ./jobs/ directory
    untracked_list = sorted(
        list(filter(lambda f: f.endswith('perf'), os.listdir(pcs.get_job_directory())))
    )

    # Second load registered files in job index
    job_index = pcs.get_job_index()
    index.touch_index(job_index)
    with open(job_index, 'rb+') as index_handle:
        pending_index_entries = list(index.walk_index(index_handle))

    # Iterate through the index and check if it is still in the ./jobs directory
    # In case it is still valid, we extract it into ProfileInfo and remove it from the list
    #   of files in ./jobs directory
    for index_entry in pending_index_entries:
        if index_entry.path in untracked_list:
            real_path = os.path.join(pcs.get_job_directory(), index_entry.path)
            index_info = {
                'header': {
                    'type': index_entry.type,
                    'cmd': index_entry.cmd,
                    'args': index_entry.args,
                    'workload': index_entry.workload
                },
                'collector_info': {'name': index_entry.collector},
                'postprocessors': [
                    {'name': p} for p in index_entry.postprocessors
                    ]
            }
            profile_info = profile.ProfileInfo(
                index_entry.path, real_path, index_entry.time, index_info, is_raw_profile=True
            )
            profile_list.append(profile_info)
            saved_entries.append(index_entry)
            untracked_list.remove(index_entry.path)

    # Now for every non-registered file in the ./jobs/ directory, we load the profile,
    #   extract the info and register it in the index
    for untracked_path in untracked_list:
        real_path = os.path.join(pcs.get_job_directory(), untracked_path)
        time = timestamp.timestamp_to_str(os.stat(real_path).st_mtime)

        # Load the data from JSON, which contains additional information about profile
        loaded_profile = store.load_profile_from_file(real_path, is_raw_profile=True)
        registered_checksum = store.compute_checksum(real_path.encode('utf-8'))

        # Update the list of profiles and counters of types
        profile_info = profile.ProfileInfo(
            untracked_path, real_path, time, loaded_profile, is_raw_profile=True
        )
        untracked_entry = index.INDEX_ENTRY_CONSTRUCTORS[index.INDEX_VERSION - 1](
            time, registered_checksum, untracked_path, -1, loaded_profile
        )

        profile_list.append(profile_info)
        saved_entries.append(untracked_entry)

    # We write all of the entries that are valid in the ./jobs/ directory in the index
    index.write_list_of_entries(job_index, saved_entries)

    return profile_list


@perun_log.paged_function(paging_switch=turn_off_paging_wrt_config('status'))
def status(short=False, **_):
    """Prints the status of performance control system

    :param bool short: true if the output should be short (i.e. without some information)
    """
    # Obtain both of the heads
    major_head = vcs.get_head_major_version()
    minor_head = vcs.get_minor_head()

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
        minor_version = vcs.get_minor_version_info(minor_head)
        print_minor_version_info(minor_version)

    # Print profiles
    minor_version_profiles = profile.load_list_for_minor_version(minor_head)
    untracked_profiles = get_untracked_profiles()
    maxs = calculate_maximal_lengths_for_object_list(
        minor_version_profiles + untracked_profiles, profile.ProfileInfo.valid_attributes
    )
    print_profile_info_list(minor_version_profiles, maxs, short)
    if not short:
        print("")
    print_profile_info_list(untracked_profiles, maxs, short, 'untracked')

    # Print degradation info
    degradation_list = store.load_degradation_list_for(
        pcs.get_object_directory(), minor_head
    )
    if not short:
        print("")
    perun_log.print_short_summary_of_degradations(degradation_list)
    if not short:
        print("")
        perun_log.print_list_of_degradations(degradation_list)


@lookup_minor_version
def load_profile_from_args(profile_name, minor_version):
    """
    :param Profile profile_name: profile that will be stored for the minor version
    :param str minor_version: SHA-1 representation of the minor version
    :returns dict: loaded profile represented as dictionary
    """
    # If the profile is in raw form
    if not store.is_sha1(profile_name):
        _, minor_index_file = store.split_object_name(pcs.get_object_directory(), minor_version)
        # If there is nothing at all in the index, since it is not even created ;)
        #   we returning nothing otherwise we lookup entries in index
        if not os.path.exists(minor_index_file):
            return None
        with open(minor_index_file, 'rb') as minor_handle:
            lookup_pred = lambda entry: entry.path == profile_name
            profiles = index.lookup_all_entries_within_index(minor_handle, lookup_pred)
    else:
        profiles = [profile_name]

    # If there are more profiles we should chose
    if not profiles:
        return None
    chosen_profile = profiles[0]

    # Peek the type if the profile is correct and load the json
    _, profile_name = store.split_object_name(pcs.get_object_directory(), chosen_profile.checksum)
    loaded_profile = store.load_profile_from_file(profile_name, False)

    return loaded_profile


def print_temp_files(root, **kwargs):
    """Print the temporary files in the root directory.

    :param str root: the path to the directory that should be listed
    :param kwargs: additional parameters such as sorting, output formatting etc.
    """
    # Try to load the files in the root directory
    try:
        temp.synchronize_index()
        tmp_files = temp.list_all_temps_with_details(root)
    except InvalidTempPathException as exc:
        print("Error: " + str(exc))
        return

    # Filter the files by protection level if it is set to show only certain group
    if kwargs['filter_protection'] != 'all':
        for name, level, size in list(tmp_files):
            if level != kwargs['filter_protection']:
                tmp_files.remove((name, level, size))

    # First sort by the name
    tmp_files.sort(key=itemgetter(0))
    # Now apply 'sort-by' if it differs from name:
    if kwargs['sort_by'] != 'name':
        sort_map = temp.SORT_ATTR_MAP[kwargs['sort_by']]
        tmp_files.sort(key=itemgetter(sort_map['pos']), reverse=sort_map['reverse'])

    # Print the total files size if needed
    if not kwargs['no_total_size']:
        total_size = utils.format_file_size(sum(size for _, _, size in tmp_files))
        print('Total size of all temporary files: {}'.format(
            _set_color(total_size, TEXT_EMPH_COLOUR, not kwargs['no_color']))
        )

    # Print the file records
    print_formatted_temp_files(tmp_files, not kwargs['no_file_size'],
                               not kwargs['no_protection_level'], not kwargs['no_color'])


def print_formatted_temp_files(records, show_size, show_protection, use_color):
    """Format and print temporary file records as:
    size | protection level | path from tmp/ directory

    :param list records: the list of temporary file records as tuple (size, protection, path)
    :param bool show_size: flag indicating whether size for each file should be shown
    :param bool show_protection: if set to True, show the protection level of each file
    :param bool use_color: if set to True, certain parts of the output will be colored
    """
    # Handle empty tmp/ dir
    if not records:
        cprintln('== No results in the .perun/tmp/ directory ==', 'white')
        return

    # Absolute path might be a bit too long, we remove the path component to the tmp/ directory
    prefix = len(pcs.get_tmp_directory()) + 1
    for file_name, protection, size in records:
        # Print the size of each file
        if show_size:
            print('{}'.format(_set_color(utils.format_file_size(size),
                                         TEXT_EMPH_COLOUR, use_color)),
                  end=_set_color(' | ', TEXT_WARN_COLOUR, use_color))
        # Print the protection level of each file
        if show_protection:
            if protection == temp.UNPROTECTED:
                print('{}'.format(temp.UNPROTECTED),
                      end=_set_color(' | ', TEXT_WARN_COLOUR, use_color))
            else:
                print('{}  '.format(_set_color(temp.PROTECTED, TEXT_WARN_COLOUR, use_color)),
                      end=_set_color(' | ', TEXT_WARN_COLOUR, use_color))

        # Print the file path, emphasize the directory to make it a bit more readable
        file_name = file_name[prefix:]
        file_dir = os.path.dirname(file_name)
        if file_dir:
            file_dir += os.sep
            print('{}'.format(_set_color(file_dir, TEXT_EMPH_COLOUR, use_color)), end='')
        print('{}'.format(os.path.basename(file_name)))


def _set_color(output, color, enable_coloring=True):
    """Transforms the output to colored version.

    :param str output: the output text that should be colored
    :param str color: the color
    :param bool enable_coloring: switch that allows to disable the coloring - the function is no-op

    :return str: the new colored output (if enabled)
    """
    if enable_coloring:
        return termcolor.colored(output, color, attrs=TEXT_ATTRS)
    return output


def delete_temps(path, ignore_protected, force, **kwargs):
    """Delete the temporary file(s) identified by the path. The path can be either file (= delete
    only the file) or directory (= delete files in the directory or the whole directory).

    :param str path: the path to the target file or directory
    :param bool ignore_protected: if True, protected files are ignored and not deleted, otherwise
                                  deletion process is aborted and exception is raised
    :param bool force: if True, delete also protected files
    :param kwargs: additional parameters
    """
    try:
        # Determine if path is file or directory and call the correct functions for that
        if temp.exists_temp_file(path):
            temp.delete_temp_file(path, ignore_protected, force)
        elif temp.exists_temp_dir(path):
            # We might delete only files or files + empty directories
            if kwargs['keep_directories']:
                temp.delete_all_temps(path, ignore_protected, force)
            else:
                temp.delete_temp_dir(path, ignore_protected, force)
        # The supplied path does not exist, inform the user so they can correct the path
        else:
            print("Note: The supplied path '{}' does not exist, no files deleted"
                  .format(temp.temp_path(path)))
    except (InvalidTempPathException, ProtectedTempException) as exc:
        # Invalid path or protected files encountered
        print("Error: " + str(exc))


def sync_temps():
    """Synchronizes the internal state of the index file so that it corresponds to some possible
    manual changes in the directory by the user.
    """
    temp.synchronize_index()
