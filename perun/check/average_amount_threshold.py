import perun.profile.convert as convert
__author__ = 'Tomas Fiedor'


THRESHOLD = 2.0


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

    for target_uid, target_average in target_averages.items():
        baseline_average = baseline_averages.get(target_uid, 0)
        if baseline_average:
            difference_ration = target_average / baseline_average
            if difference_ration >= THRESHOLD:
                print("Detected degradation from avg '{}' to '{}' for {} function".format(
                    baseline_average, target_average, target_uid
                ), end=' ')
                print("with no confidence at all.")
