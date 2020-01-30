""" Module contains a set of functions for fuzzing results interpretation."""

import os.path as path
import difflib
import scipy.stats.mstats as stats
import matplotlib.pyplot as plt

import perun.utils.log as log
import perun.fuzz.filesystem as filesystem

__author__ = 'Matus Liscinsky'

# Force matplotlib to not use any Xwindows backend.
plt.switch_backend('agg')

DATA_LINE_WIDTH = 4
DATA_LINE_ALPHA = 0.9
GREY_COLOR = '#555555'
MEDIAN_ALPHA = 0.7
PLOT_SIZE_X = 10
PLOT_SIZE_Y = 5
TEXT_FONTSIZE = 11
TEXT_SPACE_CONSTANT_X = 25
TEXT_SPACE_CONSTANT_Y = 40
QUARTILE_ALPHA = 0.4
QUARTILE_LINE_WIDTH = 2


def save_anomalies(anomalies, anomaly_type, file_handle):
    """Saves anomalies (faults and hangs) into the file

    :param list anomalies: list of
    :param str anomaly_type: type of the anomalies (e.g. Faults, Hangs)
    :param File file_handle: file, where the anomalies are written
    :return:
    """
    if anomalies:
        file_handle.write("{}s:\n".format(anomaly_type.capitalize()))
        for anomaly in anomalies:
            file_handle.write(
                anomaly["path"] + " " + str(anomaly["history"]) + "\n"
            )
            log.info('.')


def save_time_series(file_handle, time_series, values):
    """Saves the time series data into the file handle

    :param File file_handle: opened file handle for writing
    :param list time_series: list of times for values
    :param list values: list of values
    """
    for index, val in enumerate(values):
        file_handle.write(
            str(time_series[index]) + " " + str(val) + "\n"
        )
        log.info('.')


def save_log_files(log_dir, time_data, degradations, time_for_cov, max_covs, parents_fitness_values,
                   base_cov, hangs, faults):
    """ Saves information about fuzzing in log file. Note: refactor

    :param str log_dir: path to the output log directory
    :param list time_data: raw time data for graph showing degradations
    :param list degradations: raw degradations data for graph showing degradations
    :param list time_for_cov: raw time data for graph showing coverage growth
    :param list max_covs: raw max_cov data for graph showing coverage growth
    :param list parents_fitness_values: sorted list of parents by their fitness values
    :param int base_cov: base coverage measured on intial seeds
    :param list hangs: mutations that caused hang
    :param list faults: mutations that caused error
    """
    log.info("Saving log files")
    deg_data_file = open(log_dir + "/degradation_plot_data.txt", "w")
    cov_data_file = open(log_dir + "/coverage_plot_data.txt", "w")
    results_data_file = open(log_dir + "/results_data.txt", "w")

    save_time_series(deg_data_file, time_data, degradations)
    save_time_series(cov_data_file, time_for_cov, max_covs)

    for mut in parents_fitness_values:
        results_data_file.write(
            str(mut["value"]) + " " + str(mut["mut"]["cov"]/base_cov) + " " +
            str(mut["mut"]["deg_ratio"]) + " " + mut["mut"]["path"] + " " +
            str(mut["mut"]["history"]) + "\n"
        )
        log.info('.')
    log.done()

    save_anomalies(hangs, 'hang', results_data_file)
    log.done()
    save_anomalies(faults, 'fault', results_data_file)
    log.done()

    deg_data_file.close()
    cov_data_file.close()
    results_data_file.close()


def get_time_value(value, time_data, data):
    """Function gets time value according to measured value.

    :param numeric value: selected y-axis value
    :param list time_data: time values (x-axis)
    :param list data: measured values (y-axis)
    :return int: time value from `time_data` according to measured value from `data`
    """
    for val in zip(time_data, data):
        if val[1] >= value:
            return val[0]
    return 0


def plot_fuzz_time_series(time_data, data, filename, title, xlabel, ylabel):
    """Plots the measured values to time series graph.

    :param list time_data: time values (x-axis)
    :param list data: measured values (y-axis)
    :param str filename: name of the output .pdf file
    :param str title: title of graph
    :param str xlabel: name of x-axis
    :param str ylabel: name of y-axis
    """
    _, axis = plt.subplots(figsize=(PLOT_SIZE_X, PLOT_SIZE_Y))

    axis.set_title(title)
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)

    axis.spines['top'].set_visible(False)
    axis.spines['right'].set_visible(False)

    axis.grid(color='grey', linestyle='-', linewidth=0.5, alpha=0.2)

    st_quartile, nd_quartile, rd_quartile = stats.mquantiles(data)
    st_quartile, nd_quartile, rd_quartile = int(st_quartile), int(nd_quartile), int(rd_quartile)
    st_time = get_time_value(st_quartile, time_data, data)
    nd_time = get_time_value(nd_quartile, time_data, data)
    rd_time = get_time_value(rd_quartile, time_data, data)

    axis.axvline(x=st_time, ymin=0, ymax=1, linestyle='--',
                 linewidth=QUARTILE_LINE_WIDTH, alpha=QUARTILE_ALPHA, color='k')
    axis.axhline(y=st_quartile, xmin=0, xmax=1, linestyle='--',
                 linewidth=QUARTILE_LINE_WIDTH, alpha=QUARTILE_ALPHA, color='k')

    axis.axvline(x=nd_time, ymin=0, ymax=1, linestyle='-',
                 linewidth=QUARTILE_LINE_WIDTH, alpha=MEDIAN_ALPHA, color='r')
    axis.axhline(y=nd_quartile, xmin=0, xmax=1, linestyle='-',
                 linewidth=QUARTILE_LINE_WIDTH, alpha=MEDIAN_ALPHA, color='r')

    axis.axvline(x=rd_time, ymin=0, ymax=1, linestyle='--',
                 linewidth=QUARTILE_LINE_WIDTH, alpha=QUARTILE_ALPHA, color='k')
    axis.axhline(y=rd_quartile, xmin=0, xmax=1, linestyle='--',
                 linewidth=QUARTILE_LINE_WIDTH, alpha=QUARTILE_ALPHA, color='k')

    text_space_x = -(max(time_data)/TEXT_SPACE_CONSTANT_X)
    text_space_y = max(data)/TEXT_SPACE_CONSTANT_Y

    plt.plot(time_data, data, 'c', alpha=DATA_LINE_ALPHA,
             linewidth=DATA_LINE_WIDTH)
    plt.text(st_time + text_space_x, st_quartile + text_space_y, str(int(st_quartile)),
             fontweight='bold', color=GREY_COLOR, fontsize=TEXT_FONTSIZE)
    plt.text(nd_time + text_space_x, nd_quartile + text_space_y, str(int(nd_quartile)),
             fontweight='bold', color='red', alpha=MEDIAN_ALPHA, fontsize=TEXT_FONTSIZE)
    plt.text(rd_time + text_space_x, rd_quartile + text_space_y, str(int(rd_quartile)),
             fontweight='bold', color=GREY_COLOR, fontsize=TEXT_FONTSIZE)
    plt.savefig(filename, bbox_inches='tight', format='pdf')


def files_diff(final_results, faults, hangs, diffs_dir):
    """Creates html files showing the difference between mutations and its predecessor
    in diff unified format.

    :param list final_results: list contatining mutations causing degradation
    :param list hangs: mutations that caused hang
    :param list faults: mutations that caused error
    :param str diffs_dir: path to the directory where diffs will be stored
    """
    log.info("Computing deltas")
    for mutations in [final_results, faults, hangs]:
        for res in mutations:
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
            log.info('.')
    log.done()
