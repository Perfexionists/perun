"""Normalizer is a simple postprocessor that normalizes the values."""

from perun.utils.helpers import PostprocessStatus

__author__ = 'Tomas Fiedor'


def get_resource_type(resource):
    """
    Arguments:
        resource(dict): dictionary representing the resource

    Returns:
        str: type of the resource ('' if there is none type)
    """
    return resource['type'] if 'type' in resource.keys() else ''


def normalize_resources(resources):
    """
    Arguments:
        resources(list): list of resources
    """
    # First compute maximas per each type
    maximum_per_type = {}
    for resource in resources:
        resource_type = get_resource_type(resource)
        type_maximum = maximum_per_type.get(resource_type, None)
        if not type_maximum or type_maximum < resource['amount']:
            maximum_per_type[resource_type] = resource['amount']

    # Now normalize the values inside the profile
    for resource in resources:
        resource_type = get_resource_type(resource)
        maximum_for_resource_type = maximum_per_type[resource_type]
        resource['amount'] = \
            resource['amount'] / maximum_for_resource_type if maximum_for_resource_type != 0.0 \
            else 1.0


def postprocess(profile, **kwargs):
    """
    Arguments:
        profile(dict): json-like profile that will be preprocessed by normalizer
        kwargs(dict): keyword arguments
    """
    # Normalize global profile
    if 'global' in profile.keys():
        normalize_resources(profile['global']['resources'])

    # Normalize each snapshot
    if 'snapshots' in profile.keys():
        for snapshot in profile['snapshots']:
            normalize_resources(snapshot['resources'])

    return PostprocessStatus.OK, "", {'profile': profile}

