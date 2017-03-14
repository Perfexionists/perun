"""This module implement the top interpretation of the profile"""
__author__ = 'Radim Podola'


def get_pretty_call_trace(trace, indent=2, margin=0):
    """ Modify the call trace for pretty print
    Arguments:
        trace(list): call trace records
        indent(int): indentation
        margin(int): left margin

    Returns:
        string: modified output
    """
    output = ''

    for i, call in enumerate(trace):
        output += ' ' * margin
        output += ' ' * indent * i
        output += call['function'] + '()'
        output += '  in  ' + call['source']
        output += ':' + str(call['line'])
        output += '\n'

    return output


def get_pretty_resources(allocations, unit, indent=2):
    """ Modify the allocations for pretty print
    Arguments:
        allocations(list): allocations records
        unit(string): unit of memory
        indent(int): indentation

    Returns:
        string: modified output
    """
    output = ''

    for i, item in enumerate(allocations):
        output += '#' + str(i + 1) + ' ' + item['subtype'] + ': '
        output += str(item['amount']) + unit
        output += ' at ' + str(item['address'])

        if item['trace']:
            output += '\n' + 'by' + '\n'
            output += get_pretty_call_trace(item['trace'], indent, 3)
        else:
            output += '\n'

        output += '\n'

    return output


def get_top(profile, top):
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
        output = get_pretty_resources(allocations[:top], memory_unit, 3)
    else:
        output = get_pretty_resources(allocations, memory_unit, 3)

    return output.strip()


if __name__ == "__main__":
    pass
