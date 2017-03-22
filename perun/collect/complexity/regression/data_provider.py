""" Module for various means of data acquisition. """

from operator import itemgetter


def profile_dictionary_provider(resources):
    """ Data provider for collector profiling output

    Arguments:
        resources(list): the list of dictionaries with profiling data

    Returns:
        generator: each subsequent call returns pair: function name, data points as a list of (x, y)
    """
    # Sort the dictionaries by function name for easier traversing
    resources = sorted(resources, key=itemgetter('uid'))
    points_list = []
    function_name = resources[0]['uid']
    # Store all the points until the function name changes
    for resource in resources:
        if resource['uid'] != function_name:
            if points_list:
                # Function name changed, yield the list of data points
                yield function_name, points_list
                points_list = [(resource['structure-unit-size'], resource['amount'])]
                function_name = resource['uid']
        else:
            # Add the data point
            points_list.append((resource['structure-unit-size'], resource['amount']))
    # End of list, yield the current list
    if points_list:
        yield function_name, points_list
