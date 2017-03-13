"""This module implement the sum interpretation of the profile"""
import json

__author__ = 'Radim Podola'


def get_sum(profile, top):
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
    memory_unit = profile['header']['units']['memory']
    snapshots = profile['snapshots']
    allocations = []

    # collecting all allocations records from profile
    for snapshot in snapshots:
        allocations.extend(snapshot['resources'])

    def is_in(sum, uid):
        for i, s in enumerate(sum):
            if (s['uid']['source'] == uid['source'] and
                        s['uid']['function'] == uid['function']):
                return i

        return None

    summary = []
    for allocation in allocations:
        ind = is_in(summary, allocation['uid'])
        if ind == None:
            summary.append({'uid': allocation['uid'],
                            'sum': allocation['amount']})
        else:
            summary[ind]['sum'] += allocation['amount']

    output = ''
    for i, item in enumerate(summary):
        if i + 1 > top:
            break

        output += '#' + str(i + 1) + ' ' + item['uid']['function'] + ': '
        output += str(item['sum']) + memory_unit
        output += ' in ' + item['uid']['source']
        output += '\n\n'

    return output


if __name__ == "__main__":
    pass
