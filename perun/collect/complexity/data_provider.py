"""Module for various means of regression data acquisition. """

from operator import itemgetter
import sys
import json


def complexity_collector_provider(filename):
    """Data provider for complexity collector profiling output.

    Arguments:
        filename(string): the name of complexity profiling file

    Returns:
        generator: each subsequent call returns tuple: x points list, y points list, function name
    """
    # Get the file resources contents
    with open(filename) as f:
        data = json.load(f)
    resources = data['resources']

    # Sort the dictionaries by function name for easier traversing
    resources = sorted(resources, key=itemgetter('uid'))
    x_points_list = []
    y_points_list = []
    function_name = resources[0]['uid']
    # Store all the points until the function name changes
    for resource in resources:
        if resource['uid'] != function_name:
            if x_points_list:
                # Function name changed, yield the list of data points
                yield x_points_list, y_points_list, function_name
                x_points_list = [resource['structure-unit-size']]
                y_points_list = [resource['amount']]
                function_name = resource['uid']
        else:
            # Add the data points
            x_points_list.append(resource['structure-unit-size'])
            y_points_list.append(resource['amount'])
    # End of resources, yield the current lists
    if x_points_list:
        yield x_points_list, y_points_list, function_name


def store_profile_to_file(filename, profile):
    """Save the profile dictionary into the unified profiling format.

    Arguments:
        filename(str): the name of the profiling file
        profile(dict): the profiling dictionary to save

    """
    with open(filename, 'w') as f:
        f.write(json.dumps(profile, sort_keys=True, indent=2))

