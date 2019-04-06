"""Module for various means of regression data acquisition. """

from operator import itemgetter

import perun.profile.convert as convert


def data_provider_mapper(profile, **kwargs):
    """Unified data provider for various profile types.

    :param dict profile: the loaded profile dictionary
    :param dict kwargs: additional parameters for data provider
    :returns generator: generator object created by specific provider function
    """
    profile_type = profile['header']['type']
    return _PROFILE_MAPPER.get(profile_type, generic_profile_provider)(profile, **kwargs)


def resource_sort_key(resource):
    """Extracts the key from resource used for sorting

    :param dict resource: profiling resource
    :return: key used for sorting
    """
    return convert.flatten(resource['uid'])


def generic_profile_provider(profile, of_key, per_key, **_):
    """Data provider for trace collector profiling output.

    :param Profile profile: the trace profile dictionary
    :param str of_key: key for which we are finding the model
    :param str per_key: key of the independent variable
    :param dict _: rest of the key arguments
    :returns generator: each subsequent call returns tuple: x points list, y points list, function
        name
    """
    # Get the file resources contents
    resources = list(map(itemgetter(1), profile.all_resources()))

    # Sort the dictionaries by function name for easier traversing
    resources = sorted(resources, key=resource_sort_key)
    x_points_list = []
    y_points_list = []
    function_name = convert.flatten(resources[0]['uid'])
    # Store all the points until the function name changes
    for resource in resources:
        if convert.flatten(resource['uid']) != function_name:
            if x_points_list:
                # Function name changed, yield the list of data points
                yield x_points_list, y_points_list, function_name
                x_points_list = [resource[per_key]]
                y_points_list = [resource[of_key]]
                function_name = convert.flatten(resource['uid'])
        else:
            # Add the data points
            x_points_list.append(resource[per_key])
            y_points_list.append(resource[of_key])
    # End of resources, yield the current lists
    if x_points_list:
        yield x_points_list, y_points_list, function_name

# profile types : data provider functions mapping dictionary
# to add new profile type - simply add new keyword and specific provider function with signature:
#  - return value: generator object that produces required profile data
#  - parameter: profile dictionary
_PROFILE_MAPPER = {
    'default': generic_profile_provider
}
