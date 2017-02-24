"""Raw printing of the profiles, i.e. without any formatting.

Raw printing is the simplest printing of the given profiles, i.e. without any
formatting and visualization techniques at all.
"""

__author__ = 'Tomas Fiedor'


def show(profile):
    """
    Arguments:
        profile(dict): dictionary profile

    Returns:
        str: string representation of the profile
    """
    RAW_INDENT = 4

    # Construct the header
    for header_item in ['type', 'minor_version', 'cmd', 'param', 'workload']:
        if header_item in profile.keys():
            print("{}: {}".format(header_item, profile[header_item]) + '')

    print('')

    # Construct the collector info
    if 'collector' in profile.keys():
        print('collector:')
        collector_info = profile['collector']
        for collector_item in ['name', 'params']:
            if collector_item in collector_info.keys():
                print(RAW_INDENT*1*' ' + "- {}: {}".format(
                    collector_item, collector_info[collector_item] or 'none'
                ))


def show_coloured(profile):
    """
    Arguments:
        profile(dict): dictionary profile

    Returns:
        str: string representation of the profile with colours
    """
    pass
