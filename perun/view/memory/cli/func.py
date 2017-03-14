"""This module implement the func interpretation of the profile"""
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

    output = get_pretty_resources(including, memory_unit, 3)

    return output.strip()


if __name__ == "__main__":
    pass
