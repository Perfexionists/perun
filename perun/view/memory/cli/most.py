"""This module implement the most interpretation of the profile"""
__author__ = 'Radim Podola'


def get_pretty_allocations(summary):
    """ Modify the allocations for pretty print
    Arguments:
        summary(list): allocations records

    Returns:
        string: modified output
    """
    output = ''
    for i, item in enumerate(summary):

        output += '#' + str(i + 1) + ' ' + item['uid']['function'] + ': '
        output += str(item['counter']) + 'x'
        output += ' in ' + item['uid']['source']
        output += '\n\n'

    return output


def get_most(profile, top):
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

    # Summary number of allocations in corresponding records
    summary = []
    for allocation in allocations:
        # free is not taken as allocation function
        if allocation['subtype'] == 'free':
            continue

        ind = is_in(summary, allocation['uid'])
        if ind is None:
            summary.append({'uid': allocation['uid'],
                            'counter': 1})
        else:
            summary[ind]['counter'] += 1

    # sorting allocations records by frequency of allocations
    summary.sort(key=lambda x: x['counter'], reverse=True)

    # cutting list length
    if len(summary) > top:
        output = get_pretty_allocations(summary[:top])
    else:
        output = get_pretty_allocations(summary)

    return output.strip()


if __name__ == "__main__":
    pass
