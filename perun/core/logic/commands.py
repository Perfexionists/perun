import os
import perun.utils.log
import perun.core.logic.store as store
__author__ = 'Tomas Fiedor'


def config(pcs, config):
    """
    Updates the configuration file @p config of the @p pcs perun file

    Arguments:
        pcs(PCS): object with performance control system wrapper
        config(config): Configuration object
    """
    perun.utils.log.msg_to_stdout("Running inner wrapper of the 'perun config'", 2)


def init_vcs(vcs_path, vcs_type, vcs_init_params):
    """
    Arguments:
        vcs_path(path): path where the vcs will be initialized
        vcs_type(str): string of the given type of the vcs repository
        vcs_init_params(list): list of additional params for initialization of the vcs

    Returns:
        bool: true if the vcs was successfully initialized at vcs_path
    """
    # 1. Dynamically find the function in vcs modules
    # 2. Call the function
    return False


def init_perun_at(perun_path, init_custom_vcs):
    """
    Arguments:
        perun_path(path): path where new perun performance control system will be stored
        init_custom_vcs(bool): true if the custom vcs should be initialized as well
    """
    perun_full_path = os.path.join(perun_path, '.perun')
    os.mkdir(perun_full_path)
    store.touch_file(os.path.join(perun_full_path, 'config.ini'))
    os.mkdir(os.path.join(perun_full_path, 'profiles'))
    os.mkdir(os.path.join(perun_full_path, 'cache'))

    # Initialization of the custom (manual) version control system
    if init_custom_vcs:
        custom_vcs_path = os.path.join(perun_full_path, 'vcs')
        os.mkdir(custom_vcs_path)
        os.mkdir(os.path.join(custom_vcs_path, 'objects'))
        os.mkdir(os.path.join(custom_vcs_path, 'tags'))
        store.touch_file(os.path.join(custom_vcs_path, 'HEAD'))

    perun.utils.log.msg_to_stdout("Initialized empty Perun repository in {}".format(perun_path), 0)


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
        if not init_vcs(kwargs['init_vcs_url'], kwargs['init_vcs_type'], kwargs['init_vcs_params']):
            perun.utils.log.error("Could not initialize empty {} repository at {}".format(
                kwargs['init_vcs_type'], kwargs['init_vcs_url']
            ))

    # init perun directory
    # FIXME: Check if there already exists a perun repository
    init_perun_at(dst, kwargs['init_vcs_type'] == 'pvcs')

    # register new performance control system in config
    # TODO: IMPLEMENT


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
