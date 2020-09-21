""" The wrapper for invoking angr tool since Perun currently runs on Python 3.5 which is
incompatible with angr atm.

"""


import os
import json

import perun.logic.temp as temp
import perun.logic.stats as stats
import perun.utils as utils
from perun.utils.helpers import SuppressedExceptions
from perun.utils.exceptions import StatsFileNotFoundException


def extract(stats_name, binary, cache, **kwargs):
    """ Extract the Call Graph and Control Flow Graph representation using the angr framework.

    When caching is enabled and the current project version already has a call graph object
    stored in the 'stats' directory, the cached version is used instead of extracting.

    :param str stats_name: name of the call graph stats file name
    :param str binary: path to the binary executable file
    :param bool cache: sets the cache on / off mode
    :param kwargs: additional optional parameters

    :return dict: the extracted and transformed CG and CFG dictionaries
    """
    # Attempt to retrieve the call graph for the given configuration if it already exists
    if cache:
        with SuppressedExceptions(StatsFileNotFoundException):
            return stats.get_stats_of(stats_name, ['perun_cg']).get('perun_cg', {})
    # Otherwise extract the call graph using angr
    with temp.TempFile('optimization/angr_call_graph.json') as cg_json, \
            temp.TempFile('optimization/angr_config.json') as angr_config:
        # TODO: add new parameter to this function that will be parameters dictionary
        config = {
            'project': binary,
            'result': cg_json.abspath,
            'libs': kwargs.get('libs', []),
            'restricted_search': kwargs.get('restricted_search', True)
        }
        with open(angr_config.abspath, 'w') as config_handle:
            json.dump(config, config_handle, indent=2)

        providers_dir = os.path.dirname(os.path.realpath(__file__))
        angr_provider = os.path.join(providers_dir, 'angr_provider.py')
        cmd = '{} {} {}'.format('python3.6', angr_provider, angr_config.abspath)
        utils.run_safely_external_command(cmd)
        with open(cg_json.abspath, 'r') as cg_handle:
            return json.load(cg_handle)
