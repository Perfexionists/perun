import os

__author__ = 'Tomas Fiedor'


def touch_file(touched_filename, times=None):
    """
    Corresponding implementation of touch inside python.
    Courtesy of:
    http://stackoverflow.com/questions/1158076/implement-touch-using-python

    Arguments:
        touched_filename(str): filename that will be touched
        times(time): access times of the file
    """
    with open(touched_filename, 'a'):
        os.utime(touched_filename, times)


def path_to_subpath(path):
    """
    Breaks path to all the subpaths, i.e. all of the prefixes of the given path.

    >>> path_to_subpath('/dir/subdir/subsubdir')
    ['/dir', '/dir/subdir', '/dir/subdir/subsubdir']

    Arguments:
        path(str): path separated by os.sep separator

    Returns:
        list: list of subpaths
    """
    assert os.path.isdir(path)
    components = path.split(os.sep)
    return [os.sep.join(components[:till]) for till in range(1, len(components) + 1)]
