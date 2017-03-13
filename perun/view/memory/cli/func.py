"""This module implement the func interpretation of the profile"""


__author__ = 'Radim Podola'


def get_func(profile, function, get_all):
    """ Get allocations of specified function only

        Parse the profile records, filter them by specified
        function participation in the allocations,
        and also modify the output to be pretty
        to write into console. Only number of top
        records are processed.
    Arguments:
        profile(dict): memory profile with records
        function(string): specified function to filter out
        get_all(bool): specify if also partial participation process

    Returns:
        string: modified output
    """
    return "func"


if __name__ == "__main__":
    pass
