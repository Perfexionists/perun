"""Normalizer is a simple postprocessor that normalizes the values."""

import click

import perun.core.logic.runner as runner

from perun.utils.helpers import PostprocessStatus, pass_profile

__author__ = 'Tomas Fiedor'


def get_resource_type(resource):
    """Checks if the resource has defined type and returns empty type otherwise.

    Checks if there is 'type' defined inside the resource, and if so then returns
    the type. Otherwise it returns empty string as a type.

    Arguments:
        resource(dict): dictionary representing the resource

    Returns:
        str: type of the resource ('' if there is none type)
    """
    return resource['type'] if 'type' in resource.keys() else ''


def normalize_resources(resources):
    """Normalize the global and snapshot resources according to the maximal values.

    Computes the maximal values per each type inside the snapshot of the resource,
    and then normalizes the values to the interval <0,1>.

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


def postprocess(profile, **_):
    """
    Arguments:
        profile(dict): json-like profile that will be preprocessed by normalizer
    """
    # Normalize global profile
    if 'global' in profile.keys():
        normalize_resources(profile['global']['resources'])

    # Normalize each snapshot
    if 'snapshots' in profile.keys():
        for snapshot in profile['snapshots']:
            normalize_resources(snapshot['resources'])

    return PostprocessStatus.OK, "", {'profile': profile}


@click.command()
@pass_profile
def normalizer(profile):
    """Normalization of the resources to the interval <0,1>."""
    runner.run_postprocessor_on_profile(profile, 'normalizer', {})
