"""Commands is a core of the perun implementation containing the basic commands.

Commands contains implementation of the basic commands of perun pcs. It is meant
to be run both from GUI applications and from CLI, where each of the function is
possible to be run in isolation.
"""

import inspect
import os

import perun.utils.decorators as decorators
import perun.utils.log as perun_log
import perun.core.logic.store as store
import perun.core.logic.config as perun_config
import perun.core.vcs as vcs

from perun.core.logic.pcs import PCS
__author__ = 'Tomas Fiedor'


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
            arg_list[minor_version_position] = vcs.get_minor_head(pcs.wrapped_vcs_type, pcs.path)
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
def add(pcs, profile, minor_version):
    """Appends @p profile to the @p minor_version inside the @p pcs

    Arguments:
        pcs(PCS): object with performance control system wrapper
        profile(Profile): profile that will be stored for the minor version
        minor_version(str): SHA-1 representation of the minor version
    """
    assert minor_version is not None and "Missing minor version specification"

    perun_log.msg_to_stdout("Running inner wrapper of the 'perun add' with args {}, {}, {}".format(
        pcs, profile, minor_version
    ), 2)

    # Load profile content
    with open(profile, 'r', encoding='utf-8') as profile_handle:
        profile_content = "".join(profile_handle.readlines())

    # Append header to the content of the file
    header = "profile {}\0".format(len(profile_content))
    profile_content = (header + profile_content).encode('utf-8')

    # Transform to internal representation - file as sha1 checksum and content packed with zlib
    profile_sum = store.compute_checksum(profile_content)
    compressed_content = store.pack_content(profile_content)

    # Add to control
    store.add_loose_object_to_dir(pcs.get_object_directory(), profile_sum, compressed_content)

    # Register in the minor_version index
    store.register_in_index(pcs.get_object_directory(), minor_version, profile, profile_sum)


@pass_pcs
@lookup_minor_version
def remove(pcs, profile, minor_version):
    """Removes @p profile from the @p minor_version inside the @p pcs

    TODO: There are actually several possible combinations how this could be called:
    1) Stating the sha1 precisely (easy)
      - but fuck you have to remove it from index you dork...
    2) Stating the minor version and file name
      - have to lookup the minor version and get the sha1 for the filename
    3) Removing all?

    Arguments:
        pcs(PCS): object with performance control system wrapper
        profile(Profile): profile that will be stored for the minor version
        minor_version(str): SHA-1 representation of the minor version
    """
    assert minor_version is not None and "Missing minor version specification"

    perun_log.msg_to_stdout("Running inner wrapper of the 'perun rm'", 2)

    store.remove_loose_object_from_dir(pcs.get_object_directory(), profile)

    store.remove_from_index(minor_version, profile)


@pass_pcs
def log(pcs):
    """
    Prints the log of the @p pcs

    Arguments:
        pcs(PCS): object with performance control system wrapper
    """
    perun_log.msg_to_stdout("Running inner wrapper of the 'perun log '", 2)


@pass_pcs
def show(pcs, profile, minor_version, **kwargs):
    """
    Arguments:
        pcs(PCS): object with performance control system wrapper
        profile(Profile): profile that will be stored for the minor version
        minor_version(str): SHA-1 representation of the minor version
        kwargs(dict): keyword atributes containing additional options
    """
    perun_log.msg_to_stdout("Running inner wrapper of the 'perun show'", 2)


@pass_pcs
def run(pcs, **kwargs):
    """
    Arguments:
        pcs(PCS): object with performance control system wrapper
        kwargs(dict): dictionary of keyword arguments
    """
    pass
