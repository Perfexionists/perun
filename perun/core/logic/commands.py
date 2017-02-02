import perun.utils.log
__author__ = 'Tomas Fiedor'


def config(pcs, config):
    """
    Updates the configuration file @p config of the @p pcs perun file

    Arguments:
        pcs(PCS): object with performance control system wrapper
        config(config): Configuration object
    """
    perun.utils.log.msg_to_stdout("Running inner wrapper of the 'perun config'", 2)


def init(pcs):
    """
    Inits the performance control system at a given directory. Optionally inits the
    wrapper of the Version Control System that is used as tracking point.

    Arguments:
        pcs(PCS): object with performance control system wrapper
    """
    perun.utils.log.msg_to_stdout("Running inner wrapper of the 'perun init'", 2)


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
