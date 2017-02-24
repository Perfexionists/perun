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
import perun.core.logic.store as store
import perun.core.vcs as vcs

from perun.utils.helpers import MAXIMAL_LINE_WIDTH, TEXT_EMPH_COLOUR, TEXT_ATTRS, TEXT_WARN_COLOUR
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
                pcs.vcs_type, pcs.vcs_url)
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

    # init the wrapping repository as well
    if kwargs['init_vcs_type'] is not None:
        if not vcs.init(kwargs['init_vcs_type'], kwargs['init_vcs_url'], kwargs['init_vcs_params']):
            perun_log.error("Could not initialize empty {} repository at {}".format(
                kwargs['init_vcs_type'], kwargs['init_vcs_url']
            ))

    # Construct local config
    vcs_config = {
        'vcs': {
            'url': kwargs['init_vcs_url'] or "../",
            'type': kwargs['init_vcs_type'] or 'pvcs'
        }
    }

    # check if there exists perun directory above and initialize the new pcs
    super_perun_dir = find_perun_dir_on_path(dst)
    is_reinit = (super_perun_dir == dst)

    if not is_reinit and super_perun_dir != "":
        perun_log.warn("There exists super perun directory at {}".format(super_perun_dir))
    init_perun_at(dst, kwargs['init_vcs_type'] == 'pvcs', is_reinit, vcs_config)

    # register new performance control system in config
    if not is_reinit:
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
        unpacked_profile = profile.load_profile_from_file(profile_name)
        assert 'type' in unpacked_profile.keys()

    # Append header to the content of the file
    header = "profile {} {}\0".format(unpacked_profile['type'], len(profile_content))
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
def remove(pcs, profile, minor_version, **kwargs):
    """Removes @p profile from the @p minor_version inside the @p pcs

    Arguments:
        pcs(PCS): object with performance control system wrapper
        profile(Profile): profile that will be stored for the minor version
        minor_version(str): SHA-1 representation of the minor version
        kwargs(dict): dictionary with additional options
    """
    assert minor_version is not None and "Missing minor version specification"

    perun_log.msg_to_stdout("Running inner wrapper of the 'perun rm'", 2)

    object_directory = pcs.get_object_directory()
    store.remove_from_index(object_directory, minor_version, profile, kwargs['remove_all'])


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

    # Walk the minor versions and print them
    for minor in vcs.walk_minor_versions(pcs.vcs_type, pcs.vcs_url, minor_version)[::-1]:
        if kwargs['short_minors']:
            print_short_minor_version_info(pcs, minor)
        else:
            print(termcolor.colored("Minor Version {}".format(
                minor.checksum
            ), TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS))
            tracked_profiles = store.get_profile_number_for_minor(
                pcs.get_object_directory(), minor.checksum)
            if tracked_profiles:
                print("Tracked profiles: {}".format(tracked_profiles))
            else:
                print(termcolor.colored('(no tracked profiles)', TEXT_WARN_COLOUR, attrs=TEXT_ATTRS))
            print_minor_version_info(minor)


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
    short_description = minor_version.desc.split("\n")[0].ljust(MAXIMAL_LINE_WIDTH)
    if len(short_description) > MAXIMAL_LINE_WIDTH:
        short_description = short_description[:MAXIMAL_LINE_WIDTH-3] + "..."
    print(termcolor.colored("{}".format(
        short_checksum
    ), TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS), end='')
    print(" {0} ".format(short_description), end='')
    if tracked_profiles:
        print(termcolor.colored("(", 'grey', attrs=TEXT_ATTRS), end='')
        print(termcolor.colored("{}".format(
            tracked_profiles
        ), TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS), end='')
        print(termcolor.colored(" profile{})".format(
            's' if tracked_profiles != 1 else ''
        ), 'grey', attrs=TEXT_ATTRS))
    else:
        print(termcolor.colored('(no profiles)', TEXT_WARN_COLOUR, attrs=TEXT_ATTRS))


def print_minor_version_info(head_minor_version):
    """
    Arguments:
        head_minor_version(str): identification of the commit (preferably sha1)
    """
    print("Author: {0.author} <{0.email}> {0.date}".format(head_minor_version))
    for parent in head_minor_version.parents:
        print("Parent: {}".format(parent))
    print("")
    print(head_minor_version.desc)


def print_minor_version_profiles(pcs, minor_version):
    """
    Arguments:
        pcs(PCS): performance control system
        minor_version(str): identification of the commit (preferably sha1)
    """
    profiles = store.get_profile_list_for_minor(pcs.get_object_directory(), minor_version)
    print("Tracked profiles:\n" if profiles else termcolor.colored(
        "(no tracked profiles)", TEXT_WARN_COLOUR, attrs=TEXT_ATTRS))
    for index_entry in profiles:
        _, profile_name = store.split_object_name(pcs.get_object_directory(), index_entry.checksum)
        profile_type = profile.peek_profile_type(profile_name)
        print("\t{0.path} [{1}] ({0.time})".format(
            index_entry, profile_type
        ))


@pass_pcs
def status(pcs, **kwargs):
    """Prints the status of performance control system
    Arguments:
        pcs(PCS): performance control system
        kwargs(dict): dictionary of keyword arguments
    """
    # Get major head and print the status.
    major_head = vcs.get_head_major_version(pcs.vcs_type, pcs.vcs_url)
    print("On major version {} ".format(
        termcolor.colored(major_head, TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS)
    ), end='')

    # Print the index of the current head
    minor_head = vcs.get_minor_head(pcs.vcs_type, pcs.vcs_url)
    print("(minor version: {})".format(
        termcolor.colored(minor_head, TEXT_EMPH_COLOUR, attrs=TEXT_ATTRS)
    ))

    # Print in long format, the additional information about head commit
    print("")
    if not kwargs['short']:
        minor_version = vcs.get_minor_version_info(pcs.vcs_type, pcs.vcs_url, minor_head)
        print_minor_version_info(minor_version)

    # Print profiles
    print_minor_version_profiles(pcs, minor_head)


@pass_pcs
@lookup_minor_version
def show(pcs, profile, minor_version, **kwargs):
    """
    Arguments:
        pcs(PCS): object with performance control system wrapper
        profile(Profile): profile that will be stored for the minor version
        minor_version(str): SHA-1 representation of the minor version
        kwargs(dict): keyword atributes containing additional options
    """
    perun_log.msg_to_stdout("Running inner wrapper of the 'perun show'", 2)
    print("Show {} at {}".format(profile, minor_version))


@pass_pcs
def run(pcs, **kwargs):
    """
    Arguments:
        pcs(PCS): object with performance control system wrapper
        kwargs(dict): dictionary of keyword arguments
    """
    pass
