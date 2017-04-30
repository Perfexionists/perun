""" This module implements the modifying output functions """
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
        string: modified output, stripped of following empty lines
    """
    margin = 3
    output = ''

    for i, item in enumerate(allocations):
        output += '#' + str(i + 1) + ' ' + item['subtype'] + ': '
        output += str(item['amount']) + unit
        output += ' at ' + str(item['address'])

        if item['trace']:
            output += '\n' + 'by' + '\n'
            output += get_pretty_call_trace(item['trace'], indent, margin)
        else:
            output += '\n'

        output += '\n'

    return output.strip()


def get_pretty_allocations(summary, unit):
    """ Modify the allocations for pretty print
    Arguments:
        summary(list): allocations records
        unit(string): unit of summary factor

    Returns:
        string: modified output
    """
    output = ''
    for i, item in enumerate(summary):

        output += '#' + str(i + 1) + ' ' + item['uid']['function'] + ': '
        output += str(item['sum']) + unit
        output += ' in ' + item['uid']['source']
        output += '\n\n'

    return output.strip()


def get_profile_info(profile):
    """ Create the profile information output

    Arguments:
        profile(dict): the memory profile

    Returns:
        string: modified output
    """
    output = 'Information were collected and analyzed '
    output += 'from the following execution of the binary:' + '\n'
    output += profile['header']['cmd'] + ' ' + profile['header']['params']
    output += ' ' + profile['header']['workload'] + '\n'
    output += 'by ' + profile['collector']['name'] + ' collector run with '
    output += 'following parameters: ' + profile['collector']['params'] + '\n'

    return output


if __name__ == "__main__":
    pass
