"""
Module name
"""

__author__ = "Tomas Fiedor"


class VersionControlSystem(object):
    """Highest unit in the Perun version hierarchy
    
    Version control system represents the topmost class that encapsulates
    smaller major version units. The VCS corresponds to a concrete project
    for which we are tracking the profiles

    Example:
        In GIT Version control, this corresponds to a single repository
    """

    def __init__(self, vcs_id):
        """
        Attributes:
            vcs_id(str): unique idetifier of the version control unit
            vcs_type(str): type of the version control
            _major_versions(dictionary): dictionary of (name: major_version)
        """
        self.vcs_type = ""
        self._vcs_id = vcs_id
        self._major_versions = {}

    @property
    def version_control_id(self):
        """Returns the unique identifier for the Version Control System"""
        return self._vcs_id

    def add_major_version(self, name, major_version):
        """
        Arguments:
            name(str): unique namefor the major version within the VCS
            major_version(MajorVersion): major version we are adding to VCS
        """
        if major_version.vcs_type != self.vcs_type:
            # FIXME: Throw Exception
            assert False and "Major Version '" \
                             + major_version.vcs_type + "' not compatible with VCS of type '" + self.vcs_type + "'"
        elif name in self._major_versions.keys():
            # FIXME: Throw Exception
            assert False and "'" + name + "' exists in VCS"

    def get_latest_major_version(self):
        """        
        Returns:
            MajorVersion: latest major version
        """
        assert False and "Called VersionControlSystem.get_latest_major_version"


class MajorVersion(object):
    """Middle unit in the Perun version hierarchy

    Major Version represents smaller units of the Version Control.
    """
    
    def __init__(self, vcs_type, mvid):
        """
        Attributes:
            mvid(str): unique name of the major version
            vcs_type(str): type of the version control
            _minor_versions(dictionary): dictionary of (name: minor_version)
        """
        self.vcs_type = vcs_type
        self._mvid = mvid
        self._minor_versions = {}

    @property
    def major_version_id(self):
        """Returns the unique identifier for the Major Version"""
        return self._mvid

    def add_minor_version(self, name, minor_version):
        """
        Arguments:
            name(string): unique name for the minor version within the major version
            minor_version(MinorVersion): minor version we are adding to Major Version
        """
        pass

    def get_latest_minor_version(self):
        """
        Returns:
            MinorVersion: latest minor version
        """
        assert False and "Called MajorVersion.get_latest_minor_version"

        
class MinorVersion(object):
    """Minor version"""
    
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
        self.vcs_type = vcs_type 
        self.vid = vid
        self.brief = brief
        self.description = description
        self.author = author
        self.date = vdate