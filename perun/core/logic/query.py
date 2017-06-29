__author__ = 'Tomas Fiedor'


def all_resources_of(profile):
    """Generator of resources from the performance profile.

    Iterates through all of the snapshots and global resources.
    TODO: Make this dynamic by caching

    Arguments:
        profile(dict): valid profile with resources

    Returns:
        dict: yields resources per each snapshot and global section
    """
    for snapshot in profile['snapshots']:
        for resource in snapshot['resources']:
            yield resource

    for resource in profile['global']:
        yield resource


def nested_keys(key, value):
    """Generator of names for the nested keys in order to flatten the profile

    All of the nested dictionaries are flattend so all of the keys are of form:
      'key'(:'key')*

    Arguments:
        key(str): name of the base key
        value(object): dict[key] = value, i.e. the value for the given key in some dict

    Returns:
        str: stream of keys with processed nested attributes
    """
    yield key

    if type(value) == dict:
        for value_key in value.keys():
            for nested_key in nested_keys(value_key, value[value_key]):
                yield key + ":" + nested_key


def all_resource_fields_of(profile):
    """Generator of all names of the fields occurring in the resources.

    Arguments:
        profile(dict): valid profile with resources

    Returns:
        resource: stream of resource field keys
    """
    resource_fields = set()
    for resource in all_resources_of(profile):
        for key in resource.keys():
            if key not in resource_fields:
                for nested_key in nested_keys(key, resource[key]):
                    resource_fields.add(nested_key)
                    yield nested_key
