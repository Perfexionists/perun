"""
Currently just a dummy layer for Git Version Control system
"""

__author__ = "Tomas Fiedor"


def _init(vcs_path, vcs_type, vcs_init_params):
    """
    Arguments:
        vcs_path(path): path where the vcs will be initialized
        vcs_type(str): string of the given type of the vcs repository
        vcs_init_params(list): list of additional params for initialization of the vcs

    Returns:
        bool: true if the vcs was successfully initialized at vcs_path
    """
    return False


def _get_minor_head(git_path):
    """
    Arguments:
        git_path(path): path to git, where we are obtaining head for minor version
    """
    pass
