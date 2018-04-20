""" The `Average Amount Threshold` groups all of the resources according to the unique identifier
(uid; e.g. the function name) and then computes the averages of resource amounts as performance
representants of baseline and target profiles. The computed averages are then compared (by division
, and according to the set threshold the checker detects either ``Optimization`` or ``Degradation``
(the threshold is ``2.0`` ratio for detecting degradation and ``0.5`` ratio for detecting
optimization, i.e. the threshold is two times speed-up or speed-down)

  - **Detects**: `Ratio` changes; ``Optimization`` and ``Degradation``
  - **Confidence**: `None`
  - **Limitations**: `None`

The example of output generated by `AAT` method is as follows::

    * 1eb3d6: Fix the degradation of search
    |\
    | * 7813e3: Implement new version of search
    |   > collected by complexity+regression_analysis for cmd: '$ mybin'
    |     > applying 'average_amount_threshold' method
    |       - Optimization         at SLList_search(SLList*, int)
    |           from: 60677.98ms -> to: 135.29ms
    |
    * 7813e3: Implement new version of search
    |\
    | * 503885: Fix minor issues
    |   > collected by complexity+regression_analysis for cmd: '$ mybin'
    |     > applying 'average_amount_threshold' method
    |       - Degradation          at SLList_search(SLList*, int)
    |           from: 156.48ms -> to: 60677.98ms
    |
    * 503885: Fix minor issues

In the output above, we detected the ``Optimization`` between commits ``1eb3d6`` (target) and
``7813e3`` (baseline), where the average amount of running time for ``SLList_search`` function
changed from about six seconds to hundred miliseconds. For these detected changes we report no
confidence at all.
"""

import perun.profile.convert as convert
import perun.check.factory as check

from perun.utils.structs import DegradationInfo

__author__ = 'Tomas Fiedor'

DEGRADATION_THRESHOLD = 2.0
OPTIMIZATION_THRESHOLD = 0.5


def get_averages(profile):
    """Retrieves the averages of all amounts grouped by the uid

    :param dict profile: dictionary representation of profile
    :returns: dictionary with averages for all uids
    """
    data_frame = convert.resources_to_pandas_dataframe(profile)
    return data_frame.groupby('uid').mean().to_dict()['amount']


def average_amount_threshold(baseline_profile, target_profile):
    """Checks between pair of (baseline, target) profiles, whether the can be degradation detected

    This is based on simple heuristic, where for the same function models, we only check the order
    of the best fit models. If these differ, we detect the possible degradation.

    :param dict baseline_profile: baseline against which we are checking the degradation
    :param dict target_profile: profile corresponding to the checked minor version
    :returns: tuple (degradation result, degradation location, degradation rate)
    """
    baseline_averages = get_averages(baseline_profile)
    target_averages = get_averages(target_profile)

    # Fixme: Temporary solution ;)
    unit = list(baseline_profile['header']['units'].values())[0]
    resource_type = baseline_profile['header']['type']
    for target_uid, target_average in target_averages.items():
        baseline_average = baseline_averages.get(target_uid, 0)
        if baseline_average:
            difference_ration = target_average / baseline_average
            if difference_ration >= DEGRADATION_THRESHOLD:
                change = check.PerformanceChange.Degradation
            elif difference_ration <= OPTIMIZATION_THRESHOLD:
                change = check.PerformanceChange.Optimization
            else:
                change = check.PerformanceChange.NoChange

            yield DegradationInfo(
                change, resource_type, target_uid,
                "{}{}".format(baseline_average.round(2), unit),
                "{}{}".format(target_average.round(2), unit)
            )