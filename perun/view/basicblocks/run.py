"""Sunburst graph representing the basic blocks and function run-times along with execution counts.
"""

from dataclasses import dataclass

import click
import os
from perun.profile.factory import pass_profile, Profile
import perun.profile.convert as convert
import bokeh.palettes as palettes
from bokeh.plotting import figure, save, output_file
from bokeh.layouts import row, column
import numpy as np
import pandas as pd
from typing import List, Optional


@dataclass
class BasicBlockData:

    def __init__(self, time: int, execs: int, lines: List[int], file: str):
        self.time = time
        self.execs = execs
        self.src_lines = lines
        self.src_file = file

        self.runtime_percentage = 0
        self.execs_percentage = 0

    def __repr__(self):
        return (
            f"\n\t\t\ttime: {self.time}, execs: {self.execs}"
            f"\n\t\t\truntime_percentage: {self.runtime_percentage}"
            f"\n\t\t\texecs_percentage: {self.execs_percentage}"
            f"\n\t\t\tlocation: {self.src_lines} (lines) in {self.src_file}"
        )


class FunctionData:

    def __init__(
        self,
        name: str,
        time: int = 0,
        execs: int = 0,
        basic_blocks: Optional[List[BasicBlockData]] = None,
    ) -> None:
        self.name = name
        self.time = time
        self.execs = execs
        self.basic_blocks = basic_blocks if basic_blocks else []

        # time spent exclusively in the function calculated from basic block time
        self.exclusive_time = 0

        # percentage group of the function that discloses the time spent in the function compared
        # to other functions
        self.function_time_percentage_group = 0
        self.function_execs_percentage_group = 0

    def sort_basic_blocks(self, sort_by: str = "time") -> None:
        self.basic_blocks = sorted(
            self.basic_blocks,
            key=lambda bbl: bbl.time if sort_by == "time" else bbl.execs,
            reverse=True,
        )

    def __repr__(self):
        basic_blocks: str = ",".join(
            [f"\n\t\ttop{i}: {bbl}" for i, bbl in enumerate(self.basic_blocks)]
        )
        return (
            f"Function {self.name}:"
            f"\n\ttime: {self.time}, exclusive: {self.exclusive_time}"
            f"\n\texecs: {self.execs}"
            f"\n\ttime_percentage_group: {self.function_time_percentage_group},"
            f" execs_percentage_group: {self.function_execs_percentage_group}"
            f"\n\tbasic_blocks: {basic_blocks}"
        )


def convert_to_internal_representation(data: pd.DataFrame) -> List[FunctionData]:
    function_data_frame: pd.DataFrame = data[~data["uid"].str.match(r"^BBL#.*#[0-9]+")]
    function_names: List[str] = function_data_frame.uid.unique()

    functions_data: List[FunctionData] = []
    for func_name in function_names:
        # How much time was spent in function and how many times was the function called
        func_time_deltas: List[int] = function_data_frame[
            function_data_frame["uid"] == func_name
        ].amount.values
        func_time: int = sum(func_time_deltas)
        func_execs: int = len(func_time_deltas)
        func: FunctionData = FunctionData(func_name, func_time, func_execs)

        # How much time was spent in functions basic blocks and how many times were they executed
        func_bbls_data_frame: pd.DataFrame = data[data["uid"].str.match(f"^BBL#{func_name}#[0-9]+")]
        bbl_names: List[str] = func_bbls_data_frame.uid.unique()
        bbls: List[BasicBlockData] = []
        for bbl_name in bbl_names:
            bbl_data: pd.Series = func_bbls_data_frame[func_bbls_data_frame["uid"] == bbl_name]
            bbl_time_deltas: List[int] = bbl_data.amount.values
            bbl_time: int = sum(bbl_time_deltas)
            bbl_execs: int = len(bbl_time_deltas)

            bbl_src_file: str = ""
            bbl_src_lines: List[int] = []
            if len(bbl_data["source-file"].values) > 0:
                bbl_src_file = bbl_data["source-file"].values[0]
            if len(bbl_data["source-lines"].values) > 0:
                lines = bbl_data["source-lines"].values[0]
                if "," in lines:
                    bbl_src_lines = [int(line) for line in lines.split(",")]
                else:
                    bbl_src_lines = [int(lines)]

            bbl: BasicBlockData = BasicBlockData(bbl_time, bbl_execs, bbl_src_lines, bbl_src_file)
            bbls.append(bbl)

        func.basic_blocks = bbls
        # exclusively spent time in the function without other function calls inside
        func.exclusive_time = sum([bbl.time for bbl in func.basic_blocks])
        functions_data.append(func)

    return functions_data


def extract_relevant_data_to_internal_representation(
    profile: Profile, top_functions: int, top_basic_blocks: int, sort_by: str
):
    data: pd.DataFrame = convert.resources_to_pandas_dataframe(profile)

    # drop unnecessary columns
    data.drop(
        columns=["type", "subtype", "time", "workload", "tid", "snapshots"], inplace=True, axis=1
    )

    if data.loc[data["uid"] == "main"].empty:
        # FIXME: exception
        raise Exception(
            "Couldn't create graphs, not enough data. Profile doesn't include main " "function."
        )

    # get start and duration of main functions for data filtering
    main_start = data.loc[data["uid"] == "main"].timestamp.values[0]
    main_duration = data.loc[data["uid"] == "main"].amount.values[0]
    main_end = main_start + main_duration

    # filter functions executed before and after main
    in_main_mask = (data["timestamp"] >= main_start) & (
        data["timestamp"] + data["amount"] <= main_end
    )
    data = data.loc[in_main_mask]

    function_data = convert_to_internal_representation(data)

    # Sort the functions as well as their basic blocks and limit them to given amount of top
    # functions and basic blocks
    # NOTE: functions are sorted by exclusive time since it is used in the visualization instead
    # of time
    function_data = function_data[:top_functions]
    function_data = sorted(
        function_data, key=lambda func: func.exclusive_time if sort_by == "time" else func.execs
    )
    all_functions_exclusive_times_sum = sum([function.exclusive_time for function in function_data])
    all_functions_executions_sum = sum([function.execs for function in function_data])
    for function in function_data:
        function.sort_basic_blocks(sort_by)
        function.basic_blocks = function.basic_blocks[:top_basic_blocks]

        # fill the missing basic blocks with dummy objects NOTE: This is needed due to the
        # character of sunburst graph creation which requires equal amount of basic blocks in
        # every function.
        # FIXME instead of comparing to given cap, count the max bbls there are
        #  after truncation and fill towards that instead
        while len(function.basic_blocks) < top_basic_blocks:
            function.basic_blocks.append(BasicBlockData(time=0, execs=0, lines=[], file=""))

        basic_block_executions_sum = sum([bbl.execs for bbl in function.basic_blocks])
        for bbl in function.basic_blocks:
            runtime_percentage = bbl.time / function.exclusive_time
            execs_percentage = bbl.execs / basic_block_executions_sum
            # NOTE: scaling down to remain in given scope, because the collected data can be a bit
            # off
            bbl.runtime_percentage = runtime_percentage if runtime_percentage < 1.0 else 1.0
            bbl.execs_percentage = execs_percentage if execs_percentage < 1.0 else 1.0

        function.function_time_percentage_group = (
            function.exclusive_time / all_functions_exclusive_times_sum * 100
        )
        function.function_execs_percentage_group = (
            function.execs / all_functions_executions_sum * 100
        )

    return function_data


def create_sunburst_graph(function_data, graph_type="time"):

    # Create color palettes
    num_of_bbls = len(function_data[0].basic_blocks)
    bbl_color = {}
    bbl_pallete = palettes.magma(num_of_bbls + 10)
    bbl_pallete = bbl_pallete[5:-5]
    for i in range(num_of_bbls):
        bbl_color[f"BBL{i+1}"] = bbl_pallete[i]

    percentage_color = {}
    colors = palettes.all_palettes["RdYlGn"][10]
    for idx, color in enumerate(colors):
        percentage_color[str((idx + 1) * 10)] = color

    width = 1000
    height = 1000
    inner_radius = 160
    outer_radius = 400 - 10

    big_angle = 2.0 * np.pi / (len(function_data) + 1)  # +1 for the annotations column
    small_angle = big_angle / (num_of_bbls * 2 + 1)

    # Prepare figure
    p = figure(
        width=width,
        height=height,
        title="",
        x_axis_type=None,
        y_axis_type=None,
        x_range=(-510, 520),
        y_range=(-510, 520),
        min_border=0,
        outline_line_color="black",
        background_fill_color="#f9f5d7",
        border_fill_color="#f9f5d7",
        toolbar_sticky=False,
    )

    p.xgrid.grid_line_color = None
    p.ygrid.grid_line_color = None

    # annular wedges
    # starting point
    # TOP - 1/2 of annotation column - COL_IDX * ITSANGLE == starting position of the column
    angles = np.pi / 2 - big_angle / 2 - np.array(range(0, len(function_data))) * big_angle
    colors = []
    func_percentage_groups: List[int] = []
    for function in function_data:
        if graph_type == "time":
            func_percentage_groups.append(function.function_time_percentage_group)
        else:
            func_percentage_groups.append(function.function_execs_percentage_group)
    for func_percentage_group in func_percentage_groups:
        percentage_group = (func_percentage_group // 10 + 1) * 10
        colors.append(percentage_color[str(int(percentage_group))])
    p.annular_wedge(0, 0, inner_radius, outer_radius, -big_angle + angles, angles, color=colors)

    # small wedges
    bbl_colum_offset_multypliers = [i for i in reversed(range(num_of_bbls * 2 + 1)) if i % 2 != 0]
    for bbl_idx, offset_multip in enumerate(bbl_colum_offset_multypliers):
        func_percentage_groups = []
        for function in function_data:
            if graph_type == "time":
                func_percentage_groups.append(function.basic_blocks[bbl_idx].runtime_percentage)
            else:
                func_percentage_groups.append(function.basic_blocks[bbl_idx].execs_percentage)

        length = inner_radius + np.array(func_percentage_groups) * (outer_radius - inner_radius)
        p.annular_wedge(
            0,
            0,
            inner_radius,
            length,
            -big_angle + angles + offset_multip * small_angle,
            -big_angle + angles + (offset_multip + 1) * small_angle,
            color=bbl_pallete[bbl_idx],
        )

    # circular axes and lables
    labels = [float(key) for key in percentage_color]

    percentage_series = [0.0, *labels]
    percentage_series = pd.Series(percentage_series) / 100
    radii = inner_radius + percentage_series * (outer_radius - inner_radius)
    p.circle(0, 0, radius=radii[1:], fill_color=None, line_color="#282828")
    p.circle(0, 0, radius=radii[0], fill_color=None, line_color="#282828")
    p.text(
        0,
        radii[:-1],
        [str(int(r)) + "%" for r in labels],
        text_font_size="9pt",
        text_align="center",
        text_baseline="middle",
    )

    # radial axes
    p.annular_wedge(
        0,
        0,
        inner_radius - 10,
        outer_radius + 10,
        -big_angle + angles,
        -big_angle + angles,
        color="black",
    )

    # function labels
    xr = outer_radius * np.cos(np.array(-big_angle / 2 + angles))
    yr = outer_radius * np.sin(np.array(-big_angle / 2 + angles))
    label_angle = np.array(-big_angle / 2 + angles)
    label_angle[label_angle < -np.pi / 2] += np.pi  # easier to read labels on the left side
    p.text(
        xr,
        yr,
        np.array([function.name for function in function_data]),
        angle=label_angle,
        text_font_size="11pt",
        text_font_style="bold",
        text_align="center",
        text_baseline="middle",
    )

    fclx_rect = [-90 + i * 20 for i in range(10)]
    fcly_rect = [0] * 10

    p.rect(fclx_rect, fcly_rect, width=20, height=15, color=list(percentage_color.values()))
    p.text(
        [-100, 80],
        [-20, -20],
        text=["0%", "100%"],
        text_font_size="10px",
        text_align="left",
        text_baseline="middle",
    )
    heading_text = "Function time" if graph_type == "time" else "Function executions"
    p.text(-100, 15, text=[heading_text], text_font_size="10pt", text_align="left")

    # Basic blocks color labels
    bblx_circle = [outer_radius + 60] * len(bbl_color)
    bblx_text = [outer_radius + 75] * len(bbl_color)
    bbly = [20 * (len(bbl_color) / 2) - 20 * i for i in range(len(bbl_color))]
    p.rect(bblx_circle, bbly, width=15, height=15, color=list(bbl_color.values()))
    p.text(
        bblx_text,
        bbly,
        text=[f"TOP{i+1}" for i in range(len(bbl_color))],
        text_font_size="10pt",
        text_align="left",
        text_baseline="middle",
    )

    p.text(
        outer_radius + 45,
        20 * (len(bbl_color) / 2 + 1) - 10,
        text=["Basic Blocks"],
        text_font_size="10pt",
        text_align="left",
    )

    heading_text = "Basic block time" if graph_type == "time" else "Basic block executions"
    p.text(0, outer_radius + 2, text=[heading_text], text_font_size="10pt", text_align="center")

    # Basic blocks mapping
    from bokeh.models import ColumnDataSource, TableColumn, DataTable

    table_data = {"function_names": [], "source_files": []}
    for function in reversed(function_data):
        table_data["function_names"].append(function.name)
        for bbl_idx, bbl in enumerate(function.basic_blocks):
            key = f"top_{bbl_idx+1}_bbls"
            if key not in table_data.keys():
                table_data[key] = []

            location: str = "Not a BBL"
            if bbl.src_lines:
                location = f"{bbl.src_lines}"

            table_data[key].append(location)
        table_data["source_files"].append(function.basic_blocks[0].src_file)

    table_data = pd.DataFrame(table_data)

    source = ColumnDataSource(table_data)
    columns: List[TableColumn] = [TableColumn(field="function_names", title="Function name")]
    for bbl_num in range(1, num_of_bbls):
        columns.append(TableColumn(field=f"top_{bbl_num}_bbls", title=f"TOP{bbl_num} BBL"))
    columns.append(TableColumn(field="source_files", title="Source file path", width=1000))

    my_table = DataTable(
        source=source,
        columns=columns,
        fit_columns=True,
        width=1950,
        height=27 * (len(function_data) + 1),
    )
    return p, my_table


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
@click.option(
    "--top-functions",
    "-tf",
    type=int,
    default=None,
    help="Limits the functions displayed to specified number to reduce clutter.",
)
@click.option(
    "--top-basic-blocks",
    "-tbb",
    type=int,
    default=7,
    help="Limits the basic blocks displayed to specified number to reduce clutter.",
)
@click.option(
    "--sort-by",
    "-sb",
    type=str,
    default="time",
    help="Decide if the top functions/basic blocks should be sorted by execution "
    "time (time) or number of executions (execs)",
)
@pass_profile
def basicblocks(profile: Profile, top_functions: int, top_basic_blocks: int, sort_by: str):

    if sort_by not in ["time", "execs"]:
        # FIXME: exception
        raise Exception("Wrong value of --sort-by option. Choose between 'time' or 'execs'.")

    output_file("bbl_viz.html", title="Functions and their basic blocks")

    data = extract_relevant_data_to_internal_representation(
        profile, top_functions, top_basic_blocks, sort_by
    )
    p1, table1 = create_sunburst_graph(data, "time")
    p2, table2 = create_sunburst_graph(data, "execs")
    p = column(row(p1, p2), table1, table2)
    save(p)

    for function in data:
        print(
            f"\n{'function name' :<20}{'BBL' :^5}{'lines' :^40}" f"{'runtime%' :^10}{'runtime':^12}"
        )
        for idx, bbl in enumerate(function.basic_blocks):
            if not os.path.isfile(bbl.src_file):
                continue

            source_code: str = _get_file_contents_by_sequence(bbl.src_file, bbl.src_lines)
            bbl_runtime_percentage_formated = f"{bbl.runtime_percentage*100:.2f}"
            print(
                f"{function.name :<20}{idx:^5}{', '.join([str(l) for l in bbl.src_lines]):^40}"
                f"{bbl_runtime_percentage_formated:^10}{bbl.time:^12}"
            )
            print(source_code)
