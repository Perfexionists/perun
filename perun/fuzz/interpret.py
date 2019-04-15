""" Module contains a set of functions for interpretation the results of fuzzing."""

__author__ = 'Matus Liscinsky'

import difflib
import numpy as np
import matplotlib.pyplot as plt
import os.path as path
import scipy.stats.mstats as stats

import perun.fuzz.filesystem as filesystem


def get_time_value(value, time_data, data):
    """Function gets time value according to measured value.
    
    :param value int|float: selected y-axis value  
    :param time_data list: time values (x-axis)
    :param data list: measured values (y-axis)
    :return int: time value from `time_data` according to measured value from `data`
    """
    for val in zip(time_data, data):
        if val[1] >= value:
            return val[0]


def plot_fuzz_time_series(time_data, data, filename):
    """Plots the measured values to time series graph.
    
    :param time_data list: time values (x-axis)
    :param data list: measured values (y-axis)
    :param filename str: name of the output .pdf file
    """
    _, ax = plt.subplots(figsize=(10, 5))

    ax.set_title('Fuzzing in time')
    ax.set_xlabel('time (s)')
    ax.set_ylabel('Degradations')

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    ax.grid(color='grey', linestyle='-', linewidth=0.5, alpha=0.2)

    q1, q2, q3 = stats.mquantiles(data)
    q1, q2, q3 = int(q1), int(q2), int(q3)
    q1_time = get_time_value(q1, time_data, data)
    q2_time = get_time_value(q2, time_data, data)
    q3_time = get_time_value(q3, time_data, data)

    ax.axvline(x=q1_time, ymin=0, ymax=1, linestyle='--',
               linewidth=2, alpha=0.4, color='k')
    ax.axhline(y=q1, xmin=0, xmax=1, linestyle='--',
               linewidth=2, alpha=0.4, color='k')

    ax.axvline(x=q2_time, ymin=0, ymax=1, linestyle='-',
               linewidth=2, alpha=0.7, color='r')
    ax.axhline(y=q2, xmin=0, xmax=1, linestyle='-',
               linewidth=2, alpha=0.7, color='r')

    ax.axvline(x=q3_time, ymin=0, ymax=1, linestyle='--',
               linewidth=2, alpha=0.4, color='k')
    ax.axhline(y=q3, xmin=0, xmax=1, linestyle='--',
               linewidth=2, alpha=0.4, color='k')

    TEXT_SPACE_X = -(max(time_data)/25)
    TEXT_SPACE_Y = max(data)/40

    plt.plot(time_data, data, 'c', alpha=0.90, linewidth=4)
    plt.text(q1_time + TEXT_SPACE_X, q1 + TEXT_SPACE_Y, str(int(q1)),
             fontweight='bold', color='#555555', fontsize=11)
    plt.text(q2_time + TEXT_SPACE_X, q2 + TEXT_SPACE_Y, str(int(q2)),
             fontweight='bold', color='red', alpha=1, fontsize=11)
    plt.text(q3_time + TEXT_SPACE_X, q3 + TEXT_SPACE_Y, str(int(q3)),
             fontweight='bold', color='#555555', fontsize=11)
    plt.savefig(filename, bbox_inches='tight', format='pdf')


def files_diff(final_results, diffs_dir):
    """Creates html files showing the difference between mutations and its predecessor
    in diff unified format.
    
    :param final_results list: list contatining mutations causing degradation
    :param diffs_dir str: path to the directory where diffs will be stored
    """
    
    for res in final_results:
        pred = open(res["predecessor"]["path"], "r").readlines()
        result = open(res["path"], "r").readlines()

        delta = difflib.unified_diff(pred, result, lineterm='')

        # split the file to name and extension
        _, file = path.split(res["path"])
        file, _ = path.splitext(file)

        diff_file_name = file + "-diff.html"

        diff = "<table>"
        for line in delta:
            diff += "<tr><td>"
            if line[0] == '-':
                diff += "<xmp style='color: red; display: inline'>" + line + "</xmp>"
            elif line[0] == '+':
                diff += "<xmp style='color: green; display: inline'>" + line + "</xmp>"
            else:
                diff += "<xmp style='display: inline'>" + line + "</xmp>"
            diff += "</td></tr>\n"
        diff += "</table>"

        open(diff_file_name, "w").writelines(diff)
        filesystem.move_file_to(diff_file_name, diffs_dir)
