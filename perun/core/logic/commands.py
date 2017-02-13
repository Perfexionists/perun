import os
import perun.utils.decorators as decorators
import perun.utils.log
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
    else:
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
    perun_directory = find_perun_dir_on_path(os.getcwd())
    pcs = PCS(perun_directory)

    def wrapper(*args, **kwargs):
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
    perun.utils.log.msg_to_stdout("Running inner wrapper of the 'perun config' with {}, {}, {}, {}".format(
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


def init_perun_at(perun_path, init_custom_vcs, is_reinit):
    """Initialize the .perun directory at given path

    Initializes or reinitializes the .perun directory at the given path.
    Additionaly, if init_custom_vcs is set to true, the custom version control
    system is initialized as well.

    Arguments:
        perun_path(path): path where new perun performance control system will be stored
        init_custom_vcs(bool): true if the custom vcs should be initialized as well
        is_reinit(bool): true if this is existing perun, that will be reinitialized
    """
    # Initialize the basic structure of the .perun directory
    perun_full_path = os.path.join(perun_path, '.perun')
    store.touch_dir(perun_full_path)
    store.touch_dir(os.path.join(perun_full_path, 'profiles'))
    store.touch_dir(os.path.join(perun_full_path, 'cache'))

    # Initialize the custom (manual) version control system
    if init_custom_vcs:
        custom_vcs_path = os.path.join(perun_full_path, 'vcs')
        store.touch_dir(custom_vcs_path)
        store.touch_dir(os.path.join(custom_vcs_path, 'objects'))
        store.touch_dir(os.path.join(custom_vcs_path, 'tags'))
        store.touch_file(os.path.join(custom_vcs_path, 'HEAD'))

    # Perun successfully created
    msg_prefix = "Reinitialized existing" if is_reinit else "Initialized empty"
    perun.utils.log.msg_to_stdout(msg_prefix + " Perun repository in {}".format(perun_path), 0)


def init(dst, **kwargs):
    """Initializes the performance and version control systems

    Inits the performance control system at a given directory. Optionally inits the
    wrapper of the Version Control System that is used as tracking point.

    Arguments:
        dst(path): path where the pcs will be initialized
        pcs(PCS): object with performance control system wrapper
    """
    perun.utils.log.msg_to_stdout("call init({}, {})".format(dst, kwargs), 2)

    # init the wrapping repository as well
    if kwargs['init_vcs_type'] is not None:
        if not vcs.init(kwargs['init_vcs_type'], kwargs['init_vcs_url'], kwargs['init_vcs_params']):
            perun.utils.log.error("Could not initialize empty {} repository at {}".format(
                kwargs['init_vcs_type'], kwargs['init_vcs_url']
            ))

    # check if there exists perun directory above and initialize the new pcs
    super_perun_dir = find_perun_dir_on_path(dst)
    is_reinit = (super_perun_dir == dst)

    if not is_reinit and super_perun_dir != "":
        perun.utils.log.warn("There exists super perun directory at {}".format(super_perun_dir))
    init_perun_at(dst, kwargs['init_vcs_type'] == 'pvcs', is_reinit)

    # register new performance control system in config
    if not is_reinit:
        global_config = perun_config.shared()
        perun_config.append_key_at_config(global_config, 'pcs', {'dir': dst})


def add(pcs, minor_version, profile):
    """
    Appends @p profile to the @p minor_version inside the @p pcs

    Arguments:
        pcs(PCS): object with performance control system wrapper
        minor_version(str): SHA-1 representation of the minor version
        profile(Profile): profile that will be stored for the minor version
    """
    perun.utils.log.msg_to_stdout("Running inner wrapper of the 'perun add'", 2)


def rm(pcs, minor_version, profile):
    """
    Removes @p profile from the @p minor_version inside the @p pcs

    Arguments:
        pcs(PCS): object with performance control system wrapper
        minor_version(str): SHA-1 representation of the minor version
        profile(Profile): profile that will be stored for the minor version
    """
    perun.utils.log.msg_to_stdout("Running inner wrapper of the 'perun rm'", 2)


def log(pcs):
    """
    Prints the log of the @p pcs

    Arguments:
        pcs(PCS): object with performance control system wrapper
    """
    perun.utils.log.msg_to_stdout("Running inner wrapper of the 'perun log '", 2)


def show(pcs, minor_version, profile):
    """
    Arguments:
        pcs(PCS): object with performance control system wrapper
        minor_version(str): SHA-1 representation of the minor version
        profile(Profile): profile that will be stored for the minor version
    """
    pass
    perun.utils.log.msg_to_stdout("Running inner wrapper of the 'perun show'", 2)
