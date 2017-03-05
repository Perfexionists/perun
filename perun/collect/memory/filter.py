"""This module provides methods for filtering the profile"""
from perun.collect.memory.parsing import parse_allocation_location

__author__ = "Radim Podola"


def remove_allocators(profile):
    """ Remove direct allocation function (malloc, calloc, ...)
        from trace record
    Arguments:
        profile(dict): dictionary including "snapshots" and
                       "global" sections in the profile

    Returns:
        dict: updated profile
    """
    if 'snapshots' not in profile.keys():
        return {}
    if 'global' not in profile.keys():
        return {}
    # check if there is smt to remove
    glob_res = profile['global'][0]['resources']
    if not glob_res:
        return profile
    # check if the profile wasn't already filtered
    if glob_res[0]['subtype'] != glob_res[0]['trace'][0]['function']:
        return profile

    snapshots = profile['snapshots']
    for snapshot in snapshots:

        resources = snapshot['resources']
        for res in resources:
            # removing allocator
            res['trace'] = res['trace'][1:]

    return profile


def trace_filter(profile, source='', function=''):
    """ Remove records in trace section matching source or function
    Arguments:
        profile(dict): dictionary including "snapshots" and
                       "global" sections in the profile

    Returns:
        dict: updated profile
    """
    if 'snapshots' not in profile.keys():
        return {}
    if 'global' not in profile.keys():
        return {}
    # check if there is smt to remove
    glob_res = profile['global'][0]['resources']
    if not glob_res:
        return profile

    def determinate(x):
        return x['source'] != source and x['function'] != function

    snapshots = profile['snapshots']
    for snapshot in snapshots:

        resources = snapshot['resources']
        for res in resources:
            # removing call records
            res['trace'] = [call for call in res['trace'] if determinate(call)]
            # updating "uid"
            res['uid'] = parse_allocation_location(res['trace'])

    return profile


def function_filter(profile, function):
    """ Remove record of specified function out of the profile
    Arguments:
        profile(dict): dictionary including "snapshots" and
                       "global" sections in the profile
        function(string): function's name to remove record of

    Returns:
        dict: updated profile
    """
    if 'snapshots' not in profile.keys():
        return {}
    if 'global' not in profile.keys():
        return {}
    # check if there is smt to remove
    glob_res = profile['global'][0]['resources']
    if not glob_res:
        return profile

    def determinate(x):
        return not x or x['function'] != function

    snapshots = profile['snapshots']
    for snapshot in snapshots:

        snapshot['resources'] = [res for res in snapshot['resources']
                                 if determinate(res['uid'])]

    if snapshots[-1]['resources']:
        profile['global'][0]['resources'] = [snapshots[-1]['resources'][-1]]
    else:
        profile['global'][0]['resources'] = []

    return profile


if __name__ == "__main__":
    pass
