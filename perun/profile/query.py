"""Functions for issuing queries over the profiles.

Queries are realized as generators of values over the profile in the dictionary format,
as specified by the manifesto.

Fixme: Add caching to ease some of the computation.
"""

import numbers

__author__ = 'Tomas Fiedor'


def all_resources_of(profile):
    """Generator of resources from the performance profile.

    Iterates through all of the snapshots and global resources.

    Arguments:
        profile(dict): valid profile with resources

    Returns:
        (int, dict): yields resources per each snapshot and global section
    """
    snapshots = profile.get('snapshots', [])
    for snap_no, snapshot in enumerate(snapshots):
        for resource in snapshot['resources']:
            yield snap_no, resource

    # Fix this asap!
    global_snapshot = profile.get('global', {})
    for resource in global_snapshot['resources']:
        yield len(snapshots), resource


def flattened_values(root_key, root_value):
    """Converts the (root_key, root_value) pair to something that can be added to table.

    Flattens all of the dictionaries to single level and <key>(:<key>)? values, lists are processed
    to comma separated representation and rest is left as it is.

    Arguments:
        root_key(str): name of the processed key, that is going to be flattened
        root_value(object): value that is flattened

    Returns:
        (key, object): either decimal, string, or something else
    """
    # Dictionary is processed recursively according to the all items that are nested
    if isinstance(root_value, dict):
        nested_values = []
        for key, value in all_items_of(root_value):
            # Add one level of hierarchy with ':'
            nested_values.append(value)
            yield root_key + ":" + key, value
        # Additionally return the overall key asi joined values of its nested stuff
        yield root_key, ":".join(map(str, nested_values))
    # Lists are merged as comma separated keys
    elif isinstance(root_value, list):
        yield root_key, ', '.join(
            ":".join(str(nested_value[1]) for nested_value in flattened_values(str(i), lv))
            for (i, lv) in enumerate(root_value)
        )
    # Rest of the values are left as they are
    else:
        yield root_key, root_value


def all_items_of(resource):
    """Generator of all (key, value) pairs in resource.

    Iterates through all of the flattened (key, value) pairs which are output.
    Arguments:
        resource(dict): dictionary with (mainly) resource fields and values

    Returns:
        (str, value): (key, value) pairs, where value is flattened to either string, or decimal
    """
    for key, value in resource.items():
        for flattened_key, flattened_value in flattened_values(key, value):
            yield flattened_key, flattened_value


def all_resource_fields_of(profile):
    """Generator of all names of the fields occurring in the resources.

    Arguments:
        profile(dict): valid profile with resources

    Returns:
        resource: stream of resource field keys
    """
    resource_fields = set()
    for (_, resource) in all_resources_of(profile):
        for key, __ in all_items_of(resource):
            if key not in resource_fields:
                resource_fields.add(key)
                yield key


def all_numerical_resource_fields_of(profile):
    """Generator of all names of the fields occurring in the resources, that takes numeric values.

    Arguments:
        profile(dict): valid profile with resources

    Returns:
        str: stream of resource fields key, that takes integer values
    """
    resource_fields = set()
    exclude_fields = set()
    for (_, resource) in all_resources_of(profile):
        for key, value in all_items_of(resource):
            # Instances that are not numbers are removed from the resource fields (i.e. there was
            # some inconsistency between value) and added to exclude for future usages
            if not isinstance(value, numbers.Number):
                resource_fields.discard(value)
                exclude_fields.add(value)
            # If we previously encountered incorrect non-numeric value for the key, we do not add
            # it as a numeric key
            elif value not in exclude_fields:
                resource_fields.add(key)

    # Yield the stream of the keys
    for key in resource_fields:
        yield key
