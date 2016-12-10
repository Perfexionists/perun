"""
Currently just a dummy layer for Git Version Control system
"""
from . import vcs

__author__ = "Tomas Fiedor"


class GitRepository(vcs.VersionControlSystem):
    """A wrapper over the single git repository"""

    def __init__(self, repo_name):
        """
        Attributes:
            repo_name(str): name of the git repository
        """
        super(GitRepository, self).__init__(__name__, repo_name)

    def get_latest_major_version(self):
        """
        Returns:
            GitBranch: branch that the HEAD is pointing to
        """
        # TODO: Return really what the git repo is pointing!
        pass


class GitBranch(vcs.MajorVersion):
    """A wrapper over the single git branch"""
    
    def __init__(self, branch_name):
        """
        Attributes:
            branch_name(str): name of the git branch
        """
        super(GitBranch, self).__init__(__name__, branch_name)

    def get_latest_minor_version(self):
        """
        Returns:
            GitCommit: commit that HEAD is pointing to
        """
        # TODO: Return really what the git repo is pointing!
        pass
        
        
class GitCommit(vcs.MinorVersion):
    """A wrapper over the single git commit"""
    
    def __init__(self, vcs_type, vid, brief, description, author, vdate):
        """
        Attributes:
            vcs_type(str): type of the version control
            vid(int, str): unique id, preferably hash, identifying the minor version
            brief(str): brief description of the minor version
            description(str): more thorough description of the minor version
            author(Author): author of the minor version (with name, email)
            vdate(date): date of the minor version
        """
        super(GitCommit, self).__init__(__name__, vcs_type, vid, brief, description, author, vdate)
