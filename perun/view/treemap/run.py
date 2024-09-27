""" Tree map of function calls
"""

import os
from typing import List, Union, Callable, Dict

import click
import pandas as pd
import plotly.graph_objects as go

from perun.profile.convert import resources_to_pandas_dataframe
from perun.profile.factory import pass_profile, Profile
from perun.utils.log import msg_to_stdout


def _extract_function_information(profile: Profile) -> pd.DataFrame:
    unique_functions = {}

    # merge the collectable data from profile resources
    for _, resource in profile.all_resources(flatten_values=True):  # NOTE: ignoring snapshot number
        # Uniqueness of a function depends on its name and the caller
        unique_function_key = resource["uid"] + "#" + resource["caller"]
        if unique_function_key not in unique_functions:
            # first occurrence of the uid with the specific caller that is not a basic block
            unique_functions[unique_function_key] = {
                "uid": resource["uid"],
                "caller": resource["caller"],
                "amount": resource["amount"],
            }
        else:
            unique_functions[unique_function_key]["amount"] += resource["amount"]
    return pd.DataFrame(unique_functions)


def _aggregate_files(locations: pd.Series):
    if locations.drop_duplicates().size > 1:
        raise Exception("Provided profile is inconsistent.")
    return locations.iloc[0]


def _aggregate_lines(lines: pd.Series):
    if lines.drop_duplicates().size > 1:
        raise Exception("Provided profile is inconsistent.")
    return lines.iloc[0] if isinstance(lines.iloc[0], str) else str(lines.iloc[0])


def _get_file_contents_by_range(file: str, start: int, end: int) -> str:
    if not os.path.isfile(file):
        return ""
    if start > end:
        start, end = end, start

    with open(file, "r") as file_handle:
        contents = file_handle.read().split("\n")[start - 1 : end - 1 + 1]
    return "\n".join(contents)


def _get_file_contents_by_sequence(file: str, lines_sequence: List[int]) -> str:
    if not os.path.isfile(file):
        return ""

    with open(file, "r") as file_handle:
        file: List[str] = file_handle.read().split("\n")
        contents: List[str] = []
        for line_number in lines_sequence:
            contents.append(f"{line_number}: " + file[line_number - 1])
    return "\n".join(contents)


@click.command()
@click.option("--depth", "-d", type=int, default=-1, help="Number of levels initially displayed.")
@click.option(
    "--graph-type",
    "-t",
    type=str,
    default="treemap",
    help="Select a type of the visualization ['treemap', 'icicle', 'sunburst'].",
)
@click.option(
    "--basic-blocks",
    "-b",
    is_flag=True,
    default=False,
    help="Includes basic blocks if they are available in the specified profile.",
)
@pass_profile
def treemap(profile: Profile, depth: int, graph_type: str, basic_blocks: bool):
    df: pd.DataFrame = resources_to_pandas_dataframe(profile)
    df = df.drop(columns=["timestamp", "time", "snapshots", "subtype", "type", "workload"])
    pd.set_option("display.max_columns", None)

    # Override basic blocks flag if expected values are not found in the dataframe
    if basic_blocks and not df["uid"].str.startswith("BBL").any():
        msg_to_stdout("[Info]: Could not detect basic blocks in profile.", 1)
        basic_blocks = False

    # Form aggregation dictionary
    aggregation = {
        "amount": "sum",
        "source-lines": _aggregate_lines,
        "source-file": _aggregate_files,
    }

    amounts: pd.DataFrame = df.groupby(["uid", "caller"]).aggregate(aggregation).reset_index()

    functions_mask: pd.DataFrame = ~amounts["uid"].str.startswith("BBL")
    basic_blocks_mask: pd.DataFrame = amounts["uid"].str.startswith("BBL")

    # Filter out the basic blocks if present and should not be displayed
    if not basic_blocks and amounts["uid"].str.startswith("BBL").any():
        amounts = amounts[functions_mask]

    if basic_blocks:
        # normalize the duration of functions based on the basic blocks to remove overhead from
        # collected values

        # set the duration of functions to 0
        amounts.loc[functions_mask, "amount"] = 0

        # propagate duration from basic blocks to the function they belong to
        for i, row in amounts[basic_blocks_mask].iterrows():
            caller = row["caller"].split("#", 1)
            if len(caller) < 2:
                caller.append("")
            function, function_caller = caller
            amounts.loc[
                ((amounts["uid"] == function) & (amounts["caller"] == function_caller)), "amount"
            ] += row["amount"]

        # propagate duration from functions to their callers
        # NOTE: needs to be propagated from the leafs to the root of the caller tree, therefore,
        # the functions are sorted by the distance from the root.
        sorted_functions: pd.DataFrame = amounts[functions_mask].sort_values(
            "caller", key=lambda x: -x.str.count("#")
        )
        for i, row in sorted_functions.iterrows():
            caller = row["caller"].split("#", 1)
            if len(caller) < 2:
                caller.append("")
            function, function_caller = caller
            same_uid_and_caller: bool = (amounts["uid"] == function) & (
                amounts["caller"] == function_caller
            )
            amounts.loc[same_uid_and_caller, "amount"] += amounts.at[i, "amount"]

    parents: List[str] = list(amounts["caller"])
    labels: List[str] = list(amounts["uid"])
    ids: List[str] = list(map(lambda x: f"{x[1]}{'#' if x[0] else ''}{x[0]}", zip(parents, labels)))

    viz_method_map: Dict[str, Callable] = {
        "treemap": go.Treemap,
        "icicle": go.Icicle,
        "sunburst": go.Sunburst,
    }

    # get source code corresponding to each basic block and add it as a column to the amounts
    # dataframe
    if basic_blocks:
        code_col = []
        for _, row in amounts.iterrows():
            if not row["uid"].startswith("BBL#"):
                code_col.append("")
                continue

            lines: Union[int, str] = row["source-lines"]
            lines_sequence: List[int] = []
            if isinstance(lines, int):
                lines_sequence = [lines]
            elif isinstance(lines, str) and lines:
                lines_sequence = [int(i) for i in lines.split(",")]

            contents = _get_file_contents_by_sequence(row["source-file"], lines_sequence)
            contents = "\n" + contents + "\n"
            code_col.append(contents.replace("\n", "<br>"))
        amounts["code"] = code_col

    fig = go.Figure(
        viz_method_map[graph_type](
            branchvalues="total",
            labels=labels,
            parents=parents,
            ids=ids,
            values=list(amounts["amount"]),
            maxdepth=depth,
            textinfo="label+percent root+percent parent+text",
            hoverinfo="label+text",
            marker_colorscale="RdBu",
        )
    )

    # add hover texts to each basic block and function
    hover_texts: List[str] = []
    for _, row in amounts.iterrows():
        formatted_time: str = f"{row['amount']:,} μs".replace(",", " ")
        hover_text: str = (
            f"File: {row['source-file']} <br>"
            f"Lines: {row['source-lines']} <br>"
            f"Time: {formatted_time}<br>"
        )
        hover_texts.append(hover_text)
    amounts["hover"] = hover_texts
    fig.update_traces(hovertext=amounts["hover"])

    # adjust the figure based on the graph type
    if graph_type == "icicle":
        fig.update_traces(tiling=dict(orientation="v", flip="y"))
    if graph_type == "treemap":
        fig.update_traces(marker=dict(cornerradius=5))
    if basic_blocks:
        fig.update_traces(text=amounts["code"])
    fig.update_layout(margin=dict(t=50, l=25, r=25, b=25))
    fig.show()

    # TODO: should the output be stored as well?
    fig.write_html("functions_runtime_viz.html")
