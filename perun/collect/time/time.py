"""Time module is a simple wrapper over command line tool time"""

from perun.utils.helpers import CollectStatus

__author__ = 'Tomas Fiedor'


def before(**kwargs):
    """Phase for initialization of time module before collecting of the data"""
    print("Before running the time collector with {}".format(kwargs))
    return CollectStatus.OK, ""


def collect(**kwargs):
    """Phase for collection of the profile data"""
    print("Collecting the time with {}".format(kwargs))
    return CollectStatus.OK, ""


def after(**kwargs):
    """Phase after the collection for minor postprocessing that needs to be done after collect"""
    print("After running the time collector with {}".format(kwargs))
    return CollectStatus.OK, ""


if __name__ == "__main__":
    pass
