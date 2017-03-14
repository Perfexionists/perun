"""This module implement the flow interpretation of the profile"""
__author__ = 'Radim Podola'


def get_flow(profile, from_time, to_time):
    """ Get allocations flow

        Parse the profile records, cut the specified timeline,
        and also modify the output to be pretty
        to write into console. Only number of top
        records are processed.
    Arguments:
        profile(dict): memory profile with records
        from_time(int): starting of timeline
        to_time(int): ending of timeline

    Returns:
        string: modified output
    """
    return "flow"


if __name__ == "__main__":
    pass
