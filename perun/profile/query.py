"""Functions for issuing queries over the profiles.

Queries are realized as generators of values over the profile in the dictionary format,
as specified by the manifesto.

Fixme: Add caching to ease some of the computation.
"""

import numbers
import perun.utils.exceptions as exceptions

__author__ = 'Tomas Fiedor'
__coauthored__ = "Jiri Pavela"


def all_resources_of(profile):
    """Generator of resources from the performance profile.

    Iterates through all of the snapshots and global resources.

    Arguments:
        profile(dict): valid profile with resources

    Returns:
        (int, dict): yields resources per each snapshot and global section
    """
    try:
        # Get snapshot resources
        snapshots = profile.get('snapshots', [])
        for snap_no, snapshot in enumerate(snapshots):
            for resource in snapshot['resources']:
                yield snap_no, resource

        # Get global resources
        resources = profile.get('global', {}).get('resources', [])
        for resource in resources:
            yield len(snapshots), resource

    except AttributeError:
        # Element is not dict-like type with get method
        raise exceptions.IncorrectProfileFormatException(
            'profile', "Expected dictionary, got different type.") from None
    except KeyError:
        # Dictionary does not contain specified key
        raise exceptions.IncorrectProfileFormatException(
            'profile', "Missing key in dictionary.") from None


def flattened_values(root_key, root_value):
    """Converts the (root_key, root_value) pair to something that can be added to table.

    Flattens all of the dictionaries to single level and <key>(:<key>)? values, lists are processed
    to comma separated representation and rest is left as it is.

    Arguments:
        root_key(str or int): name (or index) of the processed key, that is going to be flattened
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
            yield str(root_key) + ":" + key, value
        # Additionally return the overall key as joined values of its nested stuff,
        # only if root is not a list (i.e. root key is not int = index)!
        if isinstance(root_key, str):
            yield root_key, ":".join(map(str, nested_values))
    # Lists are merged as comma separated keys
    elif isinstance(root_value, list):
        yield root_key, ','.join(
            ":".join(str(nested_value[1]) for nested_value in flattened_values(i, lv))
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


def unique_resource_values_of(profile, resource_key):
    """Generator of all unique key values occurring in the resources. The key can contain ':'
    symbol indicating another level of dictionary hierarchy or '::' for list / set level,
    e.g. trace::function.

    Arguments:
        profile(dict): valid profile with resources
        resource_key(str): the resources key identifier whose unique values are returned

    Returns:
        iterable: stream of unique resource key values
    """
    for value in _unique_values_generator(profile, resource_key, all_resources_of):
        yield value


def all_key_values_of(resource, resource_key):
    """Generator of all key values in resource. The key can contain ':' symbol indicating another
    level of dictionary hierarchy or '::' for list / set level, e.g. trace::function.

    Arguments:
        resource(dict or iterable): valid dictionary with resource keys and values
        resource_key(str): the resource key identifier to search for

    Returns:
        iterable: stream of values
    """
    # Convert the key identifier to iterable hierarchy
    key_hierarchy = resource_key.split(":")

    # Iterate the hierarchy
    for level_idx, key_level in enumerate(key_hierarchy):
        if key_level == '' and isinstance(resource, (list, set)):
            # The level is list, iterate all the members recursively
            for item in resource:
                for result in all_key_values_of(item, ':'.join(key_hierarchy[level_idx + 1:])):
                    yield result
            return
        elif key_level in resource:
            # The level is dict, find key
            resource = resource[key_level]
        else:
            # No match
            return
    yield resource


def all_models_of(profile):
    """Generator of all 'models' records from the performance profile.

    Arguments:
        profile(dict): valid profile with models

    Returns:
        (int, dict): yields 'models' records
    """
    # Get models if any
    try:
        models = profile.get('global', {}).get('models', [])
    except AttributeError:
        # global is not dict-like type with get method
        raise exceptions.IncorrectProfileFormatException(
            'profile', "'global' is not a dictionary") from None

    for model_idx, model in enumerate(models):
        yield model_idx, model


def unique_model_values_of(profile, model_key):
    """Generator of all unique key values occurring in the models. The key can contain ':'
    symbol indicating another level of dictionary hierarchy or '::' for list / set level,
    e.g. trace::function.

    Arguments:
        profile(dict): valid profile with models
        model_key(str): the models key identifier whose unique values are returned

    Returns:
        iterable: stream of unique model key values
    """
    for value in _unique_values_generator(profile, model_key, all_models_of):
        yield value


def _unique_values_generator(profile, key, blocks_gen):
    """Generator of all unique values of 'key' occurring in the profile blocks generated by
    'blocks_gen'.

    Arguments:
        profile(dict): valid profile with models
        key(str): the key identifier whose unique values are returned
        blocks_gen(iterable): the data blocks generator (e.g. all_resources_of)

    Returns:
        iterable: stream of unique key values
    """
    # value can be dict, list, set etc and not only simple type, thus the list
    unique_values = list()
    for (_, resource) in blocks_gen(profile):
        # Get all values the key contains
        for value in all_key_values_of(resource, key):
            # Return only the unique ones
            if value not in unique_values:
                unique_values.append(value)
                yield value

# Todo: add optimized version for multiple key search in one go? Need to discuss interface etc.

# Guard for imports through sphinx
if __name__ == "__main__":
    pass
