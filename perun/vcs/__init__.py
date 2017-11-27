"""Wrapper over version control systems used for generic lookup of the concrete implementations.

VCS module contains modules with concrete implementations of the wrappers over the concrete version
control systems. It tries to enforce simplicity and lightweight approach in an implementation of
the wrapper.

Inside the wrapper are defined function that are used for lookup of the concrete implementations
depending of the chosen type/module, like e.g. git, svn, etc.
"""

import perun.utils.log as perun_log
from perun.utils import dynamic_module_function_call

__author__ = 'Tomas Fiedor'


def get_minor_head(vcs_type, *args, **kwargs):
    """Returns the string representation of head of current major version, i.e.
    for git this returns the massaged HEAD reference.

    This function is called mainly during the outputs of ``perun log`` and
    ``perun status`` but also during the automatic generation of profiles
    (either by ``perun run`` or ``perun collect``), where the retrieved
    identification is used as :preg:`origin`.

    :param str vcs_type: type of the underlying wrapped version control system
    :param list args: list of non-keyword arguments passed to implemenetation
        of the wrapped vcs layer
    :param dict kwargs: dictionary of keyword arguments passed to
        implementation of the wrapped vcs layer
    :returns: unique string representation of current head (usually in SHA)
    :raises ValueError: if the head cannot be retrieved from the current
        context
    """
    try:
        return dynamic_module_function_call(
            'perun.vcs', vcs_type, '_get_minor_head', *args, **kwargs
        )
    except ValueError as value_error:
        perun_log.error("could not obtain head minor version: {}".format(value_error))


def init(vcs_type, *args, **kwargs):
    """Calls the implementation of initialization of wrapped underlying version
    control system.

    The initialization should take care of both reinitialization of existing
    version control system instances and newly created instances. Init is
    called during the ``perun init`` command from command line interface.

    :param str vcs_type: type of the underlying wrapped version control system
    :param list args: list of non-keyword arguments passed to implemenetation
        of the wrapped vcs layer
    :param dict kwargs: dictionary of keyword arguments passed to
        implementation of the wrapped vcs layer
    :return: true if the underlying vcs was successfully initialized
    """
    perun_log.msg_to_stdout("Initializing {} version control with params {} and {}".format(
        vcs_type, args, kwargs
    ), 1)
    return dynamic_module_function_call(
        'perun.vcs', vcs_type, '_init', *args, **kwargs
    )


def walk_minor_versions(vcs_type, *args, **kwargs):
    """Generator of minor versions for the given major version, which yields
    the ``MinorVersion`` named tuples containing the following information:
    ``date``, ``author``, ``email``, ``checksum`` (i.e. the hash representation
    of the minor version), ``commit_description`` and ``commit_parents`` (i.e.
    other minor versions).

    Minor versions are walked through this function during the ``perun log``
    command.

    :param str vcs_type: type of the underlying wrapped version control system
    :param list args: list of non-keyword arguments passed to implemenetation
        of the wrapped vcs layer
    :param dict kwargs: dictionary of keyword arguments passed to
        implementation of the wrapped vcs layer
    :returns: iterable stream of minor version representation
    """
    perun_log.msg_to_stdout("Walking minor versions of type {}".format(
        vcs_type
    ), 1)
    return dynamic_module_function_call(
        'perun.vcs', vcs_type, '_walk_minor_versions', *args, **kwargs
    )


def walk_major_versions(vcs_type, *args, **kwargs):
    """Generator of major versions for the current wrapped repository.

    This function is currently unused, but will be needed in the future.

    :param str vcs_type: type of the underlying wrapped version control system
    :param list args: list of non-keyword arguments passed to implemenetation
        of the wrapped vcs layer
    :param dict kwargs: dictionary of keyword arguments passed to
        implementation of the wrapped vcs layer
    :returns: interable stream of major version representation
    """
    perun_log.msg_to_stdout("Walking major versions of type {}".format(
        vcs_type
    ), 1)
    return dynamic_module_function_call(
        'perun.vcs', vcs_type, '_walk_major_versions', *args, **kwargs
    )


def get_minor_version_info(vcs_type, *args, **kwargs):
    """Yields the specification of concrete minor version in form of
    the ``MinorVersion`` named tuples containing the following information:
    ``date``, ``author``, ``email``, ``checksum`` (i.e. the hash representation
    of the minor version), ``commit_description`` and ``commit_parents`` (i.e.
    other minor versions).

    This function is a non-generator alternative of
    :func:`perun.vcs.walk_minor_versions` and is used during the ``perun
    status`` output to display the specifics of minor version.

    :param str vcs_type: type of the underlying wrapped version control system
    :param list args: list of non-keyword arguments passed to implemenetation
        of the wrapped vcs layer
    :param dict kwargs: dictionary of keyword arguments passed to
        implementation of the wrapped vcs layer
    :returns: minor version named tuple
    """
    perun_log.msg_to_stdout("Getting minor version info of type {} and args {}, {}".format(
        vcs_type, args, kwargs
    ), 1)
    return dynamic_module_function_call(
        'perun.vcs', vcs_type, '_get_minor_version_info', *args, **kwargs
    )


def get_head_major_version(vcs_type, *args, **kwargs):
    """Returns the string representation of current major version of the
    wrapped repository.

    Major version is displayed during the ``perun status`` output, which shows
    the current working major version of the project.

    :param str vcs_type: type of the underlying wrapped version control system
    :param list args: list of non-keyword arguments passed to implemenetation
        of the wrapped vcs layer
    :param dict kwargs: dictionary of keyword arguments passed to
        implementation of the wrapped vcs layer
    :returns: string representation of the major version
    """
    perun_log.msg_to_stdout("Getting head major version of type {}".format(
        vcs_type
    ), 1)
    return dynamic_module_function_call(
        'perun.vcs', vcs_type, '_get_head_major_version', *args, **kwargs
    )


def check_minor_version_validity(vcs_type, *args, **kwargs):
    """Checks whether the given minor version specification corresponds to the
    wrapped version control system, and is not in wrong format.

    Minor version validity is mostly checked during the lookup of the minor
    versions from the command line interface.

    :param str vcs_type: type of the underlying wrapped version control system
    :param list args: list of non-keyword arguments passed to implemenetation
        of the wrapped vcs layer
    :param dict kwargs: dictionary of keyword arguments passed to
        implementation of the wrapped vcs layer
    :raise VersionControlSystemException: when the given minor version is
        invalid in the context of the wrapped version control system.
    """
    dynamic_module_function_call(
        'perun.vcs', vcs_type, '_check_minor_version_validity', *args, **kwargs
    )


def massage_parameter(vcs_type, *args, **kwargs):
    """Conversion function for massaging (or unifying different representations
    of objects) the parameters for version control systems.

    Massaging is mainly executed during from the command line interface, when
    one can e.g. use the references (like ``HEAD``) to specify concrete minor
    versions. Massing then unifies e.g. the references or proper hash
    representations, to just one representation for internal processing.

    :param str vcs_type: type of the underlying wrapped version control system
    :param list args: list of non-keyword arguments passed to implemenetation
        of the wrapped vcs layer
    :param dict kwargs: dictionary of keyword arguments passed to
        implementation of the wrapped vcs layer
    :returns: string representation of parameter
    """
    return dynamic_module_function_call(
        'perun.vcs', vcs_type, '_massage_parameter', *args, **kwargs
    )
