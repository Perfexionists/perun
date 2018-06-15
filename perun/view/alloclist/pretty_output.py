""" This module implements the modifying output functions """
__author__ = 'Radim Podola'


def get_pretty_call_trace(trace, indent=2, margin=0):
    """ Transforms the call trace for pretty printing in a string representation

    :param list trace: records of call traces
    :param int indent: indentation unit, per each level
    :param int margin: staring left margin
    :returns string: trace in pretty string format
    """
    output = ''

    for i, call in enumerate(trace):
        output += ' ' * margin
        output += ' ' * indent * i
        output += '\u2514'*(i != 0)
        output += call['function']
        output += '  in  ' + call['source']
        output += ':' + str(call['line'])
        output += '\n'

    return output


def get_pretty_resources(allocations, unit, indent=2):
    """ Modify the allocations for pretty print

    :param list allocations: list of allocations records
    :param string unit: unit of memory
    :param int indent: indentation unit, per each level
    :returns string: modified output, stripped of following empty lines
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

    :param list summary: list of allocations records
    :param string unit: unit of summary factor
    :returns string: modified output
    """
    output = ''
    for i, item in enumerate(summary):

        output += '#' + str(i + 1) + ' ' + item['uid']['function'] + ': '
        output += str(item['sum']) + unit
        output += ' in ' + item['uid']['source']
        output += '\n'

    return output.strip()


def get_profile_info(profile):
    """ Create the profile information output

    :param dict profile: the memory profile
    :returns string: modified output
    """
    output = 'Information were collected and analyzed '
    output += 'from the following execution of the binary:' + '\n'
    output += profile['header']['cmd'] + ' ' + profile['header']['params']
    output += ' ' + profile['header']['workload'] + '\n'
    output += 'by ' + profile['collector_info']['name'] + ' collector run with '
    output += 'following parameters: '
    output += str(profile['collector_info']['params']) + '\n'

    return output
