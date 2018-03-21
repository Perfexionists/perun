"""Clusterization postprocessing module

Currently we will try to issue the following clusterization techniques:
  1. **Sort order**---the sort order of values itself gives the cluster
  2. **Fixed window**---the cluster is represented by a fixed sized window of values
  3. **Weighted window**---the cluster is represented by a window. The size of the window is
     dependent on the values themselves.

All of the windows can be further augmented by taking into account how many percent of values are
actually taken.
"""

import operator
import itertools
import click

import perun.postprocess.clusterizer as clustering
import perun.profile.query as query
import perun.profile.convert as convert
import perun.utils as utils
import perun.utils.log as log
import perun.logic.runner as runner
from perun.utils.helpers import PostprocessStatus, pass_profile


def resource_sort_key(resource):
    """Extracts the key from resource used for sorting

    :param dict resource: profiling resource
    :return: key used for sorting
    """
    return convert.flatten(resource['uid']), resource['amount']


def resource_group_key(resource):
    """Extracts the key from resource used for grouping

    :param dict resource: profiling resource
    :return: key used for grouping
    """
    return resource['type'], resource.get('subtype', ''), convert.flatten(resource['uid'])


def print_groups(resources):
    """Helper function for printing groups of resources

    :param list resources: list of resources
    """
    groups = itertools.groupby(resources, resource_group_key)
    for group, members in groups:
        print("--- {} ---".format(group))
        for member in members:
            print(" -> {}[{}]".format(member['amount'], member.get('cluster', '?')), end='')
        print("")


def postprocess(profile, strategy, **kwargs):
    """Takes the given profile and according to the set strategy computes clusters of resources

    All of the resources are first sorted according to their uid and amounts. Then they are group
    according to their uid and for each group we compute the clusters in isolation

    :param dict profile: performance profile that will be clusterized
    :param str strategy: name of the used strategy
        (one of clustering.SUPPORTED_STRATEGIES
    :param kwargs:
    :return:
    """
    # Flatten the resources to sorted list of resources
    resources = list(map(operator.itemgetter(1), query.all_resources_of(profile)))
    resources.sort(key=resource_sort_key)

    # For debug purposes, print the results
    print_groups(resources)

    # Call the concrete strategy, for each group of resources
    groups = itertools.groupby(resources, resource_group_key)
    for group, members in groups:
        log.info("clusterizing group {}{}@{}".format(
            group[0], "({})".format(group[1]) if group[1] else "", group[2]
        ))
        utils.dynamic_module_function_call(
            'perun.postprocess.clusterizer', strategy, 'clusterize', members
        )

    # For debug purposes, print the results
    print_groups(resources)

    # Return that everything is ok
    return PostprocessStatus.OK, "Sucessfully clusterized the profile", dict(kwargs)


@click.command()
@click.option('--strategy', '-s', default=clustering.DEFAULT_STRATEGY,
              type=click.Choice(clustering.SUPPORTED_STRATEGIES),
              help="Specifies the clustering strategy, that will be applied for the profile")
@click.option('--window-height', '-wh', default=0.01,
              type=click.FLOAT, required=False,
              help="Specifies the height of the window (either fixed or proportional)")
@click.option('--relative-window-height/--fixed-window-height', '-rh/-fh', is_flag=True,
              default=True, required=False,
              help="Specifies whether the height of the window is relative to the point or absolute")
@click.option('--window-width', '-ww', default=0.01,
              type=click.FLOAT, required=False,
              help="Specifies the width of the window"
                   ", i.e. how many values will be taken by window.")
@click.option('--weightened-window-width/--fixed-window-width', '-ww/-fw', is_flag=True,
              default=True, required=False,
              help="Specifies whether the witht of the window is weightened or fixed")
@pass_profile
def clusterizer(profile, **kwargs):
    """Clusters each resource to an appropriate cluster in order to be postprocessable
    by regression analysis.

    \b
      * **Limitations**: `none`
      * **Dependencies**: `none`

    Clusterizer tries to find a suitable cluster for each resource in the profile. The clusters
    are either computed w.r.t the sort order of the amounts, or are computed according to the
    sliding window.

    The sliding window can be further adjusted by setting its width (i.e. how many near values on
    the x axis will we take to a cluster) and its height (i.e. how large is the window in regards
    of the size of amount). Both width and height can be further augmented. Width can be weightened
    by the frequency of the given value (i.e. the more values of certain amounts we have, the less
    we take). Similarly the height can be set to be relative, i.e. instead of having clusters of
    absolute size, we have a clusters of relative size (i.e. percentage of the amount).

    For more details about regression analysis refer to
    :ref:`postprocessors-clusterization`.
    """
    runner.run_postprocessor_on_profile(profile, 'clusterizer', kwargs)
