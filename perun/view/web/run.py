"""Graphical visualization of the profiles made by `web` collector"""

import os
import click
import shlex
import subprocess
import webbrowser
import numpy as np
import pandas as pd
import seaborn as sns
import holoviews as hv
import perun.profile.factory as profile_factory

from holoviews import opts
from matplotlib import pyplot as plt
from perun.utils import log as perun_log
from typing import Any, List, Union, Dict
from matplotlib.colors import LinearSegmentedColormap
from perun.view.web.unsupported_metric_exception import UnsupportedMetricException


output_dir = "view/"


def generate_route_heatmap(data: List[dict[str, Any]], metric: str, show: bool, group_by: str = "1min") -> None:
    """
    Generate a heatmap visualization of route data based on a given metric.

    Parameters:
        data (List[dict[str, Any]]): The dataset as a list of dictionaries.
        metric (str): The metric for which the heatmap is to be generated.
        show (bool): Flag indicating whether to display the heatmap in the browser.
        group_by (str, optional): The time interval for grouping the data. Defaults to "1min".

    Returns:
        None
    """

    hv.extension("bokeh")

    df = pd.DataFrame(data)
    df_filtered = df[df["type"] == metric].copy()
    df_filtered["timestamp"] = pd.to_datetime(df_filtered["timestamp"])

    df_grouped = df_filtered.groupby(["uid", pd.Grouper(key="timestamp", freq=group_by)])["amount"].mean().reset_index()
    df_grouped["timestamp"] = df_grouped["timestamp"].dt.strftime("%H:%M:%S")

    df_pivoted = df_grouped.pivot(index="uid", columns="timestamp", values="amount").fillna(0)
    df_combined = df_pivoted.stack().reset_index(name="amount")

    ds = hv.Dataset(df_combined)
    heatmap = ds.to(hv.HeatMap, ["timestamp", "uid"], "amount").sort()

    labels = hv.Labels(heatmap).opts(padding=0, text_color="skyblue")

    bg_cmap = ["black", "red", "orange", "yellow"]
    bg_cmap = LinearSegmentedColormap.from_list("bg_cmap", bg_cmap)

    title = ""

    if metric == "memory_usage_counter":
        title = "Memory (MB)"
    elif metric == "request_latency_summary":
        title = "Latency (ms)"

    heatmap.opts(opts.HeatMap(
        tools=["hover"],
        colorbar=True,
        width=800,
        toolbar="above",
        cmap=bg_cmap,
        colorbar_opts={"title": title}
        )
    )
    heatmap_opts = {
        "ylabel": "Route UID",
        "xlabel": "Time (hh:mm:ss)",
    }

    heatmap = (heatmap * labels).opts(**heatmap_opts)

    filename = output_dir + metric + "_routeHeatmap.html"
    hv.render(heatmap)
    hv.save(heatmap, filename)

    if show:
        webbrowser.open(filename)


def generate_heatmap(data: List[dict[str, Any]], metric: str, show: bool, group_by: str = "1min") -> None:
    """Heatmap for supported metrics of web collector
    You need to define labels for new metric in `get_graph_labels`, if it is not done already.
    https://holoviews.org/reference/elements/plotly/HeatMap.html

    Args:
        data (List[Dict[str, Any]]): The data to be plotted.
        metric (str): The metric to be visualized.
        show (bool): Whether to display the heatmap.
        group_by (str, optional): The time interval for grouping the data. Defaults to "20s".

    Returns:
        None
    """

    hv.extension("bokeh")

    df = pd.DataFrame(data)
    df = df[df["type"] == metric]

    # parse data
    num_bins = 6

    bin_width = (df["amount"].max() - df["amount"].min()) / num_bins
    amount_group_by = int(bin_width)

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["time_group"] = df["timestamp"].dt.floor(group_by)
    df["time"] = df["time_group"].dt.strftime("%H:%M:%S")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["amount_agg"] = (df["amount"] // amount_group_by) * amount_group_by

    df["count"] = 1

    df_agg = df.groupby(["time", "amount_agg"]).count().reset_index()

    max_count = df_agg["count"].max()
    df_agg["normalized_count"] = df_agg["count"] / max_count

    # fill missing data
    time_range = df_agg["time"].unique()
    amount_range = df_agg["amount_agg"].unique()
    index = pd.MultiIndex.from_product([time_range, amount_range], names=["time", "amount_agg"])
    df_all_combinations = pd.DataFrame(index=index).reset_index()

    df_merged = df_all_combinations.merge(df_agg, on=["time", "amount_agg"], how="left")
    df_merged.loc[:, "normalized_count"] = df_merged["normalized_count"].fillna(0)
    df_merged["normalized_count"] = df_merged["normalized_count"].clip(lower=0)

    # plot heatmap
    ds = hv.Dataset(data=df_merged, kdims=["time", "amount_agg"], vdims=["normalized_count"])
    heatmap = ds.to(hv.HeatMap, ["time", "amount_agg"], "normalized_count")

    cmap = ["black", "red", "orange", "yellow"]
    cmap = LinearSegmentedColormap.from_list("cmap", cmap)
    labels = get_graph_labels("", metric)
    y_ticks = list(range(0, int(df_merged["amount_agg"].max()) + 1, amount_group_by))

    heatmap.opts(
        opts.HeatMap(
            **labels,
            tools=["hover"],
            colorbar=True,
            width=800,
            toolbar="above",
            cmap=cmap,
            yticks=y_ticks
        )
    )

    filename = output_dir + metric + "_heatmap.html"
    hv.render(heatmap)
    hv.save(heatmap, filename)

    if show:
        webbrowser.open(filename)


def get_pairplot_labels(metric: str, amount: pd.Series, uid: pd.Series) -> pd.DataFrame:
    """Generate pairplot labels for the given metric and data.

    Parameters:
        metric (str): The metric for which labels are to be generated.
        amount (pd.Series): The amount data associated with the metric.
        uid (pd.Series): The unique identifier associated with each data point.

    Returns:
        pd.DataFrame: A DataFrame containing pairplot labels for the given metric and data.
    """
    labels = []
    for am, uid_val in zip(amount, uid):
        match metric:
            case "memory_usage_counter":
                label = {"Memory_amount (MB)": am, "Routes": uid_val}
            case "request_latency_summary":
                label = {"Latency amount (ms)": am, "Routes": uid_val}
            case "user_cpu_usage":
                label = {"User CPU Usage (s)": am, "Routes": uid_val}
            case "system_cpu_usage":
                label = {"System CPU Usage (s)": am, "Routes": uid_val}
            case "user_cpu_time":
                label = {"User CPU Time (s)": am, "Routes": uid_val}
            case "system_cpu_time":
                label = {"System CPU Time (s)": am, "Routes": uid_val}
            case "fs_read":
                label = {"FS Read": am, "Routes": uid_val}
            case "fs_write":
                label = {"FS Write": am, "Routes": uid_val}
            case "voluntary_context_switches":
                label = {"Voluntary Context Switches": am, "Routes": uid_val}
            case _:
                raise UnsupportedMetricException(f"Labels for metric {metric} are not specified")
        labels.append(label)
    return pd.DataFrame(labels)


def generate_pairplot(data: List[dict[str, Any]], metrics: List[str], show: bool, for_each_route: bool = False) -> None:
    """Generate a pairplot Matrix (SPLOM) for exploring relationships between multiple metrics in the given dataset.
       https://seaborn.pydata.org/generated/seaborn.pairplot.html

    Parameters:
        data (List[dict[str, Any]]): The dataset as a list of dictionaries.
        metrics (List[str]): List of metric to be used in pairplot.
        show (bool): Flag indicating whether to display the pairplot or not.
        for_each_route (bool) Flag indicating whether to make paiplot Figure for each route or 1 Figure for all routes.

    Returns:
        None
    """

    df = pd.DataFrame(data)

    sns.set(style="ticks", color_codes=True)

    if for_each_route:
        for route in df["uid"].unique():
            route_df = df[df["uid"] == route]
            labels = []

            for metric in metrics:
                filtered_df = route_df[route_df["type"] == metric]
                filtered_df.reset_index(drop=True, inplace=True)
                labels_metric = get_pairplot_labels(metric, filtered_df["amount"], filtered_df["uid"])
                labels.append(labels_metric)

            combined_df = pd.concat(labels)

            sns.set(rc={"figure.figsize": (5, 5)})
            sns.set_context("paper", rc={"axes.labelsize": 6})
            pairplot = sns.pairplot(combined_df, aspect=0.5, hue="Routes")

            for ax in pairplot.axes.flatten():
                ax.tick_params(axis="x", labelsize=6)
                ax.tick_params(axis="y", labelsize=6)
                ax.locator_params(axis="x", nbins=3)
                ax.locator_params(axis="y", nbins=3)

            if show:
                plt.show()

            if not route == "/":
                filename = f"{output_dir}pairplot_{route.lstrip('/').replace('/', '_')}.svg"
            else:
                filename = f"{output_dir}pairplot_root.svg"

            pairplot.savefig(filename, format="svg")
    else:
        labels = []
        for metric in metrics:
            filtered_df = df[df["type"] == metric]
            filtered_df.reset_index(drop=True, inplace=True)
            labels_metric = get_pairplot_labels(metric, filtered_df["amount"], filtered_df["uid"])
            labels.append(labels_metric)

        combined_df = pd.concat(labels)

        sns.set(rc={"figure.figsize": (5, 5)})
        sns.set_context("paper", rc={"axes.labelsize": 6})
        pairplot = sns.pairplot(combined_df, aspect=0.5, hue="Routes")

        for ax in pairplot.axes.flatten():
            ax.tick_params(axis="x", labelsize=6)
            ax.tick_params(axis="y", labelsize=6)
            ax.locator_params(axis="x", nbins=3)
            ax.locator_params(axis="y", nbins=3)

        if show:
            plt.show()

        pairplot.savefig(f"{output_dir}pairplot.svg", format="svg")


def get_graph_labels(route, metric) -> Union[dict[str, str], None]:
    """Function for graph labels for supported metrics.

    Args:
        route (str): The route for which labels are needed.
        metric (str): The metric for which labels are needed.

    Returns:
        Union[Dict[str, str], None]: A dictionary containing graph labels if supported, otherwise None.
    """
    match metric:
        case "page_requests":
            plt.xlabel("Time")
            plt.ylabel("Number of requests")
            plt.title(f"Number of requests over time - Route {route}")
        case "error_count":
            plt.xlabel("Time")
            plt.ylabel("Number of errors")
            plt.title(f"Number of errors for route {route}")
        case "memory_usage_counter":
            return {"xlabel": "Time [hh:mm:ss]", "ylabel": "Memory used [MB]", "title": "Memory heatmap"}
        case "request_latency_summary":
            return {"xlabel": "Time [hh:mm:ss]", "ylabel": "Page Latency [ms]", "title": "Latency heatmap"}
        case "fs_read":
            plt.xlabel("Time")
            plt.ylabel("File system reads")
            plt.title(f"Number of fs reads over time for all routes")
        case "fs_write":
            plt.xlabel("Time")
            plt.ylabel("File system writes")
            plt.title(f"Number of fs writes over time for all routes")
        case "voluntary_context_switches":
            plt.xlabel("Time")
            plt.ylabel("Voluntary context switches")
            plt.title(f"Number of voluntary context switches over time for all routes")
        case _:
            raise UnsupportedMetricException(f"Labels for metric {metric} are not specified")


def generate_line_graph(
        data: List[dict[str, Any]],
        metric: str,
        show: bool,
        group_by: str = "1min",
        for_all_routes: bool = False
) -> None:
    """Generate line graph for metrics without unit. Plot graph for number of occurrences.
    You need to define labels for new metric in `get_graph_labels`, if it is not done already.

    Args:
        data (List[Dict[str, Any]]): The data to be plotted.
        group_by (str): The time interval for grouping the data.
        metric (str): The metric to be visualized.
        show (bool): Whether to display the line graph.
        for_all_routes (bool) Make 1 graph for all routes combined
    Returns:
        None
    """

    df = pd.DataFrame(data)
    df.drop(columns=["time"], inplace=True)
    df.rename(columns={"amount": "value"}, inplace=True)
    df = df[df["type"] == metric]
    df = df[df["uid"] != "/favicon.ico"]

    os.makedirs(output_dir, exist_ok=True)

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["time_grouped"] = df["timestamp"].dt.floor(group_by)
    grouped_df = df.set_index("timestamp").groupby("uid").resample(group_by).size().reset_index(name="requests")

    if for_all_routes:
        plt.figure(figsize=(10, 6))

        summed_requests = grouped_df.groupby("timestamp")["requests"].sum().reset_index()

        summed_requests["timestamp"] = summed_requests["timestamp"].dt.strftime("%H:%M:%S")
        plt.plot(summed_requests["timestamp"], summed_requests["requests"])
        plt.fill_between(summed_requests["timestamp"], summed_requests["requests"], color="skyblue", alpha=0.4)

        get_graph_labels("", metric)

        plt.xticks(rotation=30)
        plt.tight_layout()

        filename = f"{output_dir}{metric}_all_routes.svg"

        plt.savefig(filename, format="svg")

        if show:
            plt.show()

        plt.close()

    else:
        for route, route_data in grouped_df.groupby("uid"):
            plt.figure(figsize=(10, 6))

            route_data["timestamp"] = route_data["timestamp"].dt.strftime("%H:%M:%S")
            plt.plot(route_data["timestamp"], route_data["requests"], label=route)
            plt.fill_between(route_data["timestamp"], route_data["requests"], color="skyblue", alpha=0.4)

            get_graph_labels(route, metric)

            plt.xticks(rotation=30)
            plt.tight_layout()

            if not route == "/":
                filename = f"{output_dir}{metric}_{route.lstrip('/').replace('/', '_')}.svg"
            else:
                filename = f"{output_dir}{metric}_root.svg"

            plt.savefig(filename, format="svg")

            if show:
                plt.show()

            plt.close()


def run_call_graph() -> None:
    """Generates simple call graph of functions of project
    Function finds all TS files in project and statically find project functions
    to create call graph.
    Credits to author of the package https://github.com/whyboris/TypeScript-Call-Graph

    Returns:
        None
    """

    find_command = "find . -type f -name '*.ts'"
    find_process = subprocess.Popen(find_command, stdout=subprocess.PIPE, shell=True)
    ts_files, _ = find_process.communicate()
    ts_files = ts_files.decode().strip().split("\n")

    printf_command = "printf 'y\n'"
    npx_tcg_command = f"npx tcg {' '.join(shlex.quote(file) for file in ts_files)}"

    process_printf = subprocess.Popen(printf_command, stdout=subprocess.PIPE, shell=True)
    subprocess.Popen(npx_tcg_command, stdin=process_printf.stdout, shell=True)


@click.command()
@click.option(
    "--group-by",
    "-g",
    default="1min",
    required=False,
    help="Group by values in graphs by period.\n"
         "The default is 1 minute.\n"
         "For example group values by:\n"
         "5s   - 5 seconds\n"
         "1min - 1 minute\n"
         "1h     - 1 hour\n"
         "1D     - 1 day\n"
)
@click.option(
    "--show",
    "-s",
    default=False,
    required=False,
    is_flag=True,
    help="Show generated graphs and call graph.\n"
         "Graphs will be saved in any case to the current directory."
)
@profile_factory.pass_profile
def web(profile: profile_factory.Profile, group_by: str, show: bool) -> None:
    """Graphs visualizing metrics collected by web collector.
       Graphs are saved to /view directory in your project

       Returns:
           None
    """

    perun_log.minor_info("Parsing profile for graphs...")

    data = profile.all_resources()
    sliced_data = [item[1] for item in data]

    perun_log.minor_info("Generating line graphs...")

    generate_line_graph(sliced_data, "page_requests", show, group_by)
    generate_line_graph(sliced_data, "fs_read", show, group_by, True)
    generate_line_graph(sliced_data, "fs_write", show, group_by, True)
    generate_line_graph(sliced_data, "voluntary_context_switches", show, group_by, True)

    perun_log.minor_info("Generating pairplot...")

    generate_pairplot(
        sliced_data,
        [
            "memory_usage_counter",
            "request_latency_summary",
            "user_cpu_usage", "system_cpu_usage",
            "user_cpu_time",
            "system_cpu_time",
            "fs_read",
            "fs_write",
            "voluntary_context_switches"
        ],
        show,
        True
    )

    perun_log.minor_info("Generating heatmaps...")

    generate_heatmap(sliced_data, "memory_usage_counter", show, group_by)

    generate_route_heatmap(sliced_data, "memory_usage_counter", show, group_by)
    generate_route_heatmap(sliced_data, "request_latency_summary", show, group_by)

    if show:
        perun_log.minor_info("Generating call graph...")
        perun_log.minor_info("This call graph works for typescript files only...")
        run_call_graph()

    perun_log.minor_info("Generating graphs finished...")
