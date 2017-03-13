"""This module implement the most interpretation of the profile"""


__author__ = 'Radim Podola'


def get_most(profile, top):
    """ Sort records by the most allocations they made

        Parse the profile records, sort them by the most
        allocations of memory they made, and also modify the output
        to be pretty to write into console. Only number of top
        records are processed.
    Arguments:
        profile(dict): memory profile with records
        top(int): number of records to process

    Returns:
        string: modified output
    """
    return "most"


if __name__ == "__main__":
    pass
