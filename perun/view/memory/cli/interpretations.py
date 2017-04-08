"""This module implements the interpretation functions of the profile"""
from decimal import Decimal
import perun.view.memory.cli.pretty_output as pretty
import perun.view.memory.cli.heap_map

__author__ = 'Radim Podola'


def get_heap(profile, **kwargs):
    """ Call interactive __heap map visualization

    Arguments:
        profile(dict): memory profile with records
        kwargs(dick): rest of unneeded arguments

    Returns:
        string: empty string
    """
    perun.view.memory.cli.heap_map.heap_map(profile)

    return ''


def get_most(profile, top, **kwargs):
    """ Sort records by the frequency of allocations they made

        Parse the profile records, sort them by the frequency of
        allocations of memory they made, and also modify the output
        to be pretty to write into console. Only number of top
        records are processed.
    Arguments:
        profile(dict): memory profile with records
        top(int): number of records to process

    Returns:
        string: modified output
    """
    snapshots = profile['snapshots']
    allocations = []
    summary_unit = 'x'

    # collecting all allocations records from profile
    for snapshot in snapshots:
        allocations.extend(snapshot['resources'])

    # Summary number of allocations in corresponding records
    summary = []
    for allocation in allocations:
        # free is not taken as allocation function
        if allocation['subtype'] == 'free':
            continue

        ind = is_uid_in(summary, allocation['uid'])
        if ind is None:
            summary.append({'uid': allocation['uid'],
                            'sum': 1})
        else:
            summary[ind]['sum'] += 1

    # sorting allocations records by frequency of allocations
    summary.sort(key=lambda x: x['sum'], reverse=True)

    # cutting list length
    if len(summary) > top:
        output = pretty.get_pretty_allocations(summary[:top], summary_unit)
    else:
        output = pretty.get_pretty_allocations(summary, summary_unit)

    return output


def get_sum(profile, top, **kwargs):
    """ Sort records by summary of the allocated memory

        Parse the profile records, sort them by summary
        of the allocated memory, and also modify the output
        to be pretty to write into console. Only number of top
        records are processed.
    Arguments:
        profile(dict): memory profile with records
        top(int): number of records to process

    Returns:
        string: modified output
    """
    # parsing unit used for amount of memory
    summary_unit = profile['header']['units']['memory']
    snapshots = profile['snapshots']
    allocations = []

    # collecting all allocations records from profile
    for snapshot in snapshots:
        allocations.extend(snapshot['resources'])

    # Summary allocated memory in corresponding records
    summary = []
    for allocation in allocations:
        # free is not taken as allocation function
        if allocation['subtype'] == 'free':
            continue

        ind = is_uid_in(summary, allocation['uid'])
        if ind is None:
            summary.append({'uid': allocation['uid'],
                            'sum': allocation['amount']})
        else:
            summary[ind]['sum'] += allocation['amount']
    # sorting allocations records by amount of summarized allocated memory
    summary.sort(key=lambda x: x['sum'], reverse=True)

    # cutting list length
    if len(summary) > top:
        output = pretty.get_pretty_allocations(summary[:top], summary_unit)
    else:
        output = pretty.get_pretty_allocations(summary, summary_unit)

    return output


def get_func(profile, function, get_all, **kwargs):
    """ Get allocations of specified function only

        Parse the profile records, filter them by specified
        function participation in the allocations,
        and also modify the output to be pretty
        to write into console. Only number of top
        records are processed.
    Arguments:
        profile(dict): memory profile with records
        function(string): specified function to filter out
        get_all(bool): specify if process also partial participation

    Returns:
        string: modified output
    """
    # parsing unit used for amount of memory
    memory_unit = profile['header']['units']['memory']
    snapshots = profile['snapshots']
    allocations = []

    # collecting all allocations records from profile
    for snapshot in snapshots:
        allocations.extend(snapshot['resources'])

    def is_function_in(summary, func):
        """ Evaluate if FUNC is included in SUMMARY
            Returns:
                bool: evaluation
        """
        for item in summary:
            if item['function'] == func:
                return True

        return False

    # search up the function in allocations records
    including = []
    for allocation in allocations:
        # free is not taken as allocation function
        if allocation['subtype'] == 'free':
            continue

        if get_all:
            res = is_function_in(allocation['trace'], function)
        else:
            res = is_function_in([allocation['uid']], function)

        if res:
            including.append(allocation)

    output = pretty.get_pretty_resources(including, memory_unit, 3)

    return output


def get_flow(profile, from_time, to_time, **kwargs):
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
    # parsing unit used for amount of memory
    memory_unit = profile['header']['units']['memory']
    snapshots = profile['snapshots']
    allocations = []

    # collecting allocations records from profile fulfilling time requirements
    for snapshot in snapshots:
        if from_time:
            if Decimal(from_time) > Decimal(snapshot['time']):
                continue
        if to_time:
            if Decimal(to_time) < Decimal(snapshot['time']):
                continue
        allocations.extend(snapshot['resources'])

    # free is not taken as allocation function
    allocations = [a for a in allocations if a['subtype'] != 'free']

    output = pretty.get_pretty_resources(allocations, memory_unit, 3)

    return output


def get_top(profile, top, **kwargs):
    """ Sort records by the amount of allocated memory

        Parse the profile records, sort them by amount
        of allocated memory, and also modify the output
        to be pretty to write into console. Only number of top
        records are processed.
    Arguments:
        profile(dict): memory profile with records
        top(int): number of records to process

    Returns:
        string: modified output
    """
    # parsing unit used for amount of memory
    memory_unit = profile['header']['units']['memory']
    snapshots = profile['snapshots']
    allocations = []

    # collecting all allocations records from profile
    for snapshot in snapshots:
        allocations.extend(snapshot['resources'])

    # free is not taken as allocation function
    allocations = [a for a in allocations if a['subtype'] != 'free']

    # sorting allocations records by amount of allocated memory
    allocations.sort(key=lambda x: x['amount'], reverse=True)

    # cutting list length
    if len(allocations) > top:
        output = pretty.get_pretty_resources(allocations[:top], memory_unit, 3)
    else:
        output = pretty.get_pretty_resources(allocations, memory_unit, 3)

    return output


def is_uid_in(summary, uid):
    """ Evaluate if UID is included in SUMMARY
    Returns:
        int: index if it's included, None if not
    """
    for i, item in enumerate(summary):
        if (item['uid']['source'] == uid['source'] and
                item['uid']['function'] == uid['function']):
            return i

    return None


if __name__ == "__main__":
    pass
