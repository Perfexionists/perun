import os
import perun.utils.log
import perun.core.logic.store as store
import perun.core.vcs as vcs
__author__ = 'Tomas Fiedor'


def config(pcs, config):
    """
    Updates the configuration file @p config of the @p pcs perun file

    Arguments:
        pcs(PCS): object with performance control system wrapper
        config(config): Configuration object
    """
    perun.utils.log.msg_to_stdout("Running inner wrapper of the 'perun config'", 2)


def init_perun_at(perun_path, init_custom_vcs, is_reinit):
    """
    Arguments:
        perun_path(path): path where new perun performance control system will be stored
        init_custom_vcs(bool): true if the custom vcs should be initialized as well
        is_reinit(bool): true if this is existing perun, that will be reinitialized
    """
    perun_full_path = os.path.join(perun_path, '.perun')
    store.touch_dir(perun_full_path)
    store.touch_file(os.path.join(perun_full_path, 'config.ini'))
    store.touch_dir(os.path.join(perun_full_path, 'profiles'))
    store.touch_dir(os.path.join(perun_full_path, 'cache'))

    # Initialization of the custom (manual) version control system
    if init_custom_vcs:
        custom_vcs_path = os.path.join(perun_full_path, 'vcs')
        store.touch_dir(custom_vcs_path)
        store.touch_dir(os.path.join(custom_vcs_path, 'objects'))
        store.touch_dir(os.path.join(custom_vcs_path, 'tags'))
        store.touch_file(os.path.join(custom_vcs_path, 'HEAD'))

    msg_prefix = "Reinitialized existing" if is_reinit else "Initialized empty"
    perun.utils.log.msg_to_stdout(msg_prefix + " Perun repository in {}".format(perun_path), 0)


def find_perun_dir_on_path(path):
    """
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


def init(dst, **kwargs):
    """
    Inits the performance control system at a given directory. Optionally inits the
    wrapper of the Version Control System that is used as tracking point.

    Arguments:
        dst(path): path where the pcs will be initialized
        pcs(PCS): object with performance control system wrapper
    """
    perun.utils.log.msg_to_stdout("call init({}, {})".format(dst, kwargs), 2)

    # init the wrapping repository as well
    if kwargs['init_vcs_type'] is not None:
        if not vcs.init(kwargs['init_vcs_url'], kwargs['init_vcs_type'], kwargs['init_vcs_params']):
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
        # TODO: IMPLEMENT
        pass


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
