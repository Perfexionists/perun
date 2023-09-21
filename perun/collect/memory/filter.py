"""This module provides methods for filtering the profile"""
import perun.collect.memory.parsing as parsing


def remove_allocators(profile: dict) -> dict:
    """ Remove records in trace with direct allocation function

        Allocators are better to remove because they are
        in all traces. Removing them makes profile clearer.

    :param dict profile: dictionary including "snapshots" and "global" sections in the profile
    :returns dict: updated profile
    """
    allocators = [
        'malloc', 'calloc', 'realloc', 'free', 'memalign', 'posix_memalign', 'valloc',
        'aligned_alloc'
    ]
    trace_filter(profile, function=allocators, source=[])

    return profile


def trace_filter(profile: dict, function: list[str], source: list[str]) -> dict:
    """ Remove records in trace section matching source or function

    :param dict profile: dictionary including "snapshots" and "global" sections in the profile
    :param list function: list of "function" records to omit
    :param list source: list of "source" records to omit
    :returns dict: updated profile
    """
    def determinate(call: dict) -> bool:
        """ Determinate expression """
        return (call['source'] not in source and
                call['function'] not in function)

    snapshots = profile['snapshots']
    for snapshot in snapshots:

        resources = snapshot['resources']
        for res in resources:
            # removing call records
            res['trace'] = [call for call in res['trace'] if determinate(call)]
            # updating "uid"
            res['uid'] = parsing.parse_allocation_location(res['trace'])

    return profile


def set_global_region(profile: dict) -> None:
    """
    :param dict profile: partially computed profile
    """
    profile['global'] = {}


def allocation_filter(profile: dict, function: list[str], source: list[str]) -> dict:
    """ Remove record of specified function or source code out of the profile

    :param dict profile: dictionary including "snapshots" and "global" sections in the profile
    :param list function: function's name to remove record of
    :param list source: source's name to remove record of
    :returns dict: updated profile
    """
    def determinate(uid: dict) -> bool:
        """ Determinate expression """
        if uid:
            if uid['function'] in function:
                return False
            if any(map(lambda s: s is not None and str(uid['source']).endswith(s), source)):
                return False
        return True

    snapshots = profile['snapshots']
    for snapshot in snapshots:
        snapshot['resources'] = [res for res in snapshot['resources'] if determinate(res['uid'])]
    set_global_region(profile)

    return profile


def remove_uidless_records_from(profile: dict) -> dict:
    """ Remove record without UID out of the profile

    :param dict profile: dictionary including "snapshots" and "global" sections in the profile
    :returns dict: updated profile
    """
    snapshots = profile['snapshots']
    for snapshot in snapshots:
        snapshot['resources'] = [res for res in snapshot['resources'] if res['uid']]

    return profile
