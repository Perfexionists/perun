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