"""This module implement the sum interpretation of the profile"""
__author__ = 'Radim Podola'


def get_pretty_allocations(summary, unit):
    """ Modify the allocations for pretty print
    Arguments:
        summary(list): allocations records
        unit(string): unit of memory

    Returns:
        string: modified output
    """
    output = ''
    for i, item in enumerate(summary):

        output += '#' + str(i + 1) + ' ' + item['uid']['function'] + ': '
        output += str(item['sum']) + unit
        output += ' in ' + item['uid']['source']
        output += '\n\n'

    return output


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

    def is_in(summary, uid):
        """ Evaluate if UID is included in SUMMARY
        Returns:
            int: index if it's included, None if not
        """
        for i, item in enumerate(summary):
            if (item['uid']['source'] == uid['source'] and
                    item['uid']['function'] == uid['function']):
                return i

        return None

    # Summary allocated memory in corresponding records
    summary = []
    for allocation in allocations:
        # free is not taken as allocation function
        if allocation['subtype'] == 'free':
            continue

        ind = is_in(summary, allocation['uid'])
        if ind is None:
            summary.append({'uid': allocation['uid'],
                            'sum': allocation['amount']})
        else:
            summary[ind]['sum'] += allocation['amount']

    # sorting allocations records by amount of summarized allocated memory
    summary.sort(key=lambda x: x['sum'], reverse=True)

    # cutting list length
    if len(summary) > top:
        output = get_pretty_allocations(summary[:top], memory_unit)
    else:
        output = get_pretty_allocations(summary, memory_unit)

    return output.strip()


if __name__ == "__main__":
    pass
