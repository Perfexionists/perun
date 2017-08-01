"""Module for various means of regression data acquisition. """

from operator import itemgetter


def data_provider_mapper(profile):
    """Unified data provider for various profile types.

    Arguments:
        profile(dict): the loaded profile dictionary

    Returns:
        generator: generator object created by specific provider function
    """
    profile_type = profile['header']['type']
    return _profile_mapper[profile_type](profile)


def complexity_profile_provider(profile):
    """Data provider for complexity collector profiling output.

    Arguments:
        profile(dict): the complexity profile dictionary

    Returns:
        generator: each subsequent call returns tuple: x points list, y points list, function name
    """
    # Get the file resources contents
    resources = profile['global']['resources']

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

# profile types : data provider functions mapping dictionary
# to add new profile type - simply add new keyword and specific provider function with signature:
#  - return value: generator object that produces required profile data
#  - parameter: profile dictionary
_profile_mapper = {
    'mixed': complexity_profile_provider
}
