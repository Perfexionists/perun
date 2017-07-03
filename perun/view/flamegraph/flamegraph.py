"""This module provides wrapper for the Flame graph visualization"""

import os
import subprocess
import perun.core.profile.converters as converter

__author__ = 'Radim Podola'
_SCRIPT_FILENAME = './flamegraph.pl'


def draw_flame_graph(profile, output_file, height):
    """ Draw Flame graph from profile.

        To create Flame graphs it's uses perl script created by Brendan Gregg.
        https://github.com/brendangregg/FlameGraph/blob/master/flamegraph.pl

    Arguments:
        profile(dict): the memory profile
        output_file(str): filename of the output file, expected is SVG format
        height(int): graphs height
    """
    # converting profile format to format suitable to Flame graph visualization
    flame = converter.create_flame_graph_format(profile)

    header = profile['header']
    profile_type = header['type']
    title = "{} consumption of {} {} {}".format(profile_type,
                                                header['cmd'],
                                                header['params'],
                                                header['workload'])
    units = header['units'][profile_type]

    pwd = os.path.dirname(os.path.abspath(__file__))
    with open(output_file, 'w') as out:
        process = subprocess.Popen([_SCRIPT_FILENAME,
                                    '--title', title,
                                    '--countname', units,
                                    '--reverse',
                                    '--height', str(height)],
                                   stdin=subprocess.PIPE,
                                   stdout=out,
                                   cwd=pwd)
        process.communicate(bytes(''.join(flame), encoding='UTF-8'))
