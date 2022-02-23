"""Sunburst graph representing the basic blocks and function run-times along with execution counts.
"""

import click
from perun.profile.factory import pass_profile, Profile
import perun.profile.convert as convert
from perun.utils.log import msg_to_stdout
import bokeh.palettes as palettes
from bokeh.plotting import figure, show, output_file
from bokeh.layouts import row
from bisect import insort, bisect
import numpy as np
import pandas as pd
from typing import Union


def get_functions_data(data: pd.DataFrame, top_basic_blocks: Union[int, None]=None, sort_by :str='time') -> dict:
    """Converts data from dataframe into records about functions instead and filters basic blocks.

    :param DataFrame data: data from which to create function information
    :param int top_basic_blocks: select how many top basic blocks to filter (optional)
    :param string sort_by: select sorting method time/execs

    :returns dict new_data: dictionary representation of filtered data
    """

    function_data = data[~data['uid'].str.match(r'^BBL#.*#[0-9]+')]
    function_names = function_data.uid.unique()

    new_data = {}
    for function_name in function_names:

        # How much time was spent in function and how many times was it called
        func_time_deltas = function_data[function_data['uid'] == function_name].amount.values
        new_data[function_name] = {'func_time': sum(func_time_deltas), 'func_execs': len(func_time_deltas),
                                   'bbl_times': [], 'bbl_execs': []}

        # How much time was spent in function's basic blocks and how many times were they executed
        func_bbls = data[data['uid'].str.match(f'^BBL#{function_name}#[0-9]+')]
        bbl_names = func_bbls.uid.unique()
        for bbl_name in bbl_names:
            bbl_data = func_bbls[func_bbls['uid'] == bbl_name]
            time_deltas = bbl_data.amount.values
            if sort_by == 'execs':
                insertion_idx = bisect(new_data[function_name]['bbl_execs'], sum(time_deltas))
                insort(new_data[function_name]['bbl_execs'], sum(time_deltas))
                new_data[function_name]['bbl_times'].insert(insertion_idx, len(time_deltas))
            else:
                insertion_idx = bisect(new_data[function_name]['bbl_times'], sum(time_deltas))
                insort(new_data[function_name]['bbl_times'], sum(time_deltas))
                new_data[function_name]['bbl_execs'].insert(insertion_idx, len(time_deltas))

        # overwrite the time of function with exclusively spent time in the function without other function calls inside
        new_data[function_name]['func_time'] = sum(new_data[function_name]['bbl_times'])

        if top_basic_blocks:
            new_data[function_name]['bbl_times'] = new_data[function_name]['bbl_times'][:top_basic_blocks]
            new_data[function_name]['bbl_execs'] = new_data[function_name]['bbl_execs'][:top_basic_blocks]

    return new_data


def get_data(profile: Profile, top_functions: int, top_basic_blocks: int, sort_by: str) -> pd.DataFrame:
    """Prepares data for sunburst plot and returns them as dataframes.

    :param Profile  profile: profile from which to extract data
    :param int top_functions: select how many top functions to include in data
    :param int top_basic_blocks: select how many top basic blocks to include in data
    :param string sort_by: select method of sorting time/execs

    :returns DataFrame, DataFrame dataframes: dataframes containing the filtered data for two different sunbursts
    """

    data = convert.resources_to_pandas_dataframe(profile)

    # drop unnecessary coumns
    data.drop(columns=['type', 'subtype', 'time', 'workload', 'tid', 'snapshots'], inplace=True, axis=1)

    # get start and duration of main functions for data filtering
    if data.loc[data['uid'] == 'main'].empty:
        # FIXME: exception
        raise Exception("Couldn't create graphs, not enough data. Profile doesn't include main function.")

    main_start = data.loc[data['uid'] == 'main'].timestamp.values[0]
    main_duration = data.loc[data['uid'] == 'main'].amount.values[0]
    main_end = main_start + main_duration

    # filter functions executed before and after main
    data = data[(data['timestamp'] >= main_start) & (data['timestamp']+data['amount'] <= main_end)]

    functions_data = get_functions_data(data, top_basic_blocks, sort_by)

    functions_data_sorted_keys = sorted(functions_data, key=lambda a: functions_data[a][f'func_{sort_by}'], reverse=True)

    df_time = create_df_from_functions_data(functions_data, time=True, main_duration=main_duration)
    df_execs = create_df_from_functions_data(functions_data)

    # apply the sort to dataframes
    df_time = df_time.set_index('function_name').loc[functions_data_sorted_keys].reset_index()
    df_execs = df_execs.set_index('function_name').loc[functions_data_sorted_keys].reset_index()

    if top_functions:
        df_time = df_time[:top_functions]
        df_execs = df_execs[:top_functions]

    # convert the values in func_percentage_group columns after filtering to actual percentages
    for df in [df_time, df_execs]:
        sum_of_col_values = df.func_percentage_group.sum()
        for i, row in df.iterrows():
            df.loc[i, 'func_percentage_group'] = (row['func_percentage_group']/sum_of_col_values)*100

    return df_time, df_execs


def create_df_from_functions_data(functions_data :dict, time :bool=False, main_duration :Union[int,None]=None) -> pd.DataFrame:
    """ Converts the function data into a data frame format suitable for sunburst plot

    :param dict functions_data: dict containing filtered information about functions
    :param bool time: flag that decides what df is being created time/execs
    :param int main_duration: selects the main duration from which are the percentages calculated

    :returns DataFrame df: dataframe with data about functions provided
    """
    # unify counts of basic blocks with zeroes so that dataframe creation is possible
    max_bbls = 0
    all_func_execs = 0
    for func_data in functions_data.values():
        # find out what is the max number of basic blocks
        current_bbls_cnt = len(func_data['bbl_times'])
        max_bbls = current_bbls_cnt if current_bbls_cnt > max_bbls else max_bbls
        # and also the number of function calls
        all_func_execs += func_data['func_execs']

    # fill the missing values with dummy zeroes
    for func_data in functions_data.values():
        while len(func_data['bbl_times']) < max_bbls:
            func_data['bbl_times'].append(0)
            func_data['bbl_execs'].append(0)

    data_frame = {'function_name': [], 'func_percentage_group': []}

    for i in range(max_bbls):
        data_frame[f'BBL{i + 1}'] = []

    for func_name, func_data in functions_data.items():

        # function_name
        data_frame['function_name'].append(func_name)

        # function_percentage_group
        if time and main_duration:
            #data_frame['func_percentage_group'].append((func_data[f'func_time'] / main_duration) * 100)
            # Store func time in this column and edit it when the size of dataframe is filtered
            # determines the percentage group from the sum of this column after the filtering
            data_frame['func_percentage_group'].append(func_data[f'func_time'])
            function_exclusive_time = sum(func_data['bbl_times'])  # time spent exclusively in the function
            for idx, bbl_run_time in enumerate(func_data['bbl_times']):
                # bbl_run_time - each run time of this basic block combined
                exclusive_bbl_runtime_percentage = bbl_run_time / function_exclusive_time
                data_frame[f'BBL{idx + 1}'].append(exclusive_bbl_runtime_percentage if exclusive_bbl_runtime_percentage <= 1.0 else 1.0)
        else:
            #data_frame['func_percentage_group'].append((func_data['func_execs'] / all_func_execs) * 100)
            # Store func execs in this column and edit it when the size of dataframe is filtered
            # determines the percentage group from the sum of this column after the filtering
            data_frame['func_percentage_group'].append(func_data['func_execs'])
            basic_block_executions_sum = sum(func_data['bbl_execs'])  # number of executions of basic blocks in the function
            for idx, bbl_exec_cnt in enumerate(func_data['bbl_execs']):
                bbl_execution_percentage = bbl_exec_cnt / basic_block_executions_sum
                data_frame[f'BBL{idx + 1}'].append(bbl_execution_percentage if bbl_execution_percentage <= 1.0 else 1.0)

    return pd.DataFrame(data_frame)


def sunburst(df:pd.DataFrame, type :str='time'):
    """ Creates a sunburst like plot. Inspired by: http://docs.bokeh.org/en/0.12.6/docs/gallery/burtin.html

    :param DataFrame df: dataframe containing information for the sunburst in correct format
    :param string type: type of sunburst graph time/execs

    :returns figure p: figure with the created sunburst
    """
    msg_to_stdout(f'[Info]:\n {df}', 2)
    bbl_columns = df.columns[2:]

    # Create color palettes
    num_of_bbls = len(bbl_columns)
    bbl_color = {}
    bbl_pallete = palettes.magma(num_of_bbls+10)
    bbl_pallete = bbl_pallete[5:-5]
    for i in range(num_of_bbls):
        bbl_color[f"BBL{i+1}"] = bbl_pallete[i]

    percentage_color = {}
    colors = palettes.all_palettes['RdYlGn'][10]
    for idx, color in enumerate(colors):
        percentage_color[str((idx+1)*10)] = color

    width = 1000
    height = 1000
    inner_radius = 160
    outer_radius = 400 - 10

    big_angle = 2.0 * np.pi / (len(df) + 1)  # +1 for the annotations column
    small_angle = big_angle / (len(bbl_columns)*2+1)

    # Prepare figure
    p = figure(plot_width=width, plot_height=height, title="",
               x_axis_type=None, y_axis_type=None,
               x_range=(-510, 520), y_range=(-510, 520),
               min_border=0, outline_line_color="black",
               background_fill_color="#f9f5d7", border_fill_color="#f9f5d7",
               toolbar_sticky=False)

    p.xgrid.grid_line_color = None
    p.ygrid.grid_line_color = None

    # annular wedges
    #[        starting point       ]
    #TOP - 1/2 of annotation column - COL_IDX * ITSANGLE == starting position of the column
    angles = np.pi / 2 - big_angle / 2 - df.index.to_series() * big_angle
    colors = []
    for func_percentage_group in df.func_percentage_group:
        percentage_group = (func_percentage_group//10+1)*10
        colors.append(percentage_color[str(int(percentage_group))])
    p.annular_wedge(0, 0, inner_radius, outer_radius, -big_angle + angles, angles, color=colors)

    # small wedges
    bbl_col_keys = bbl_columns
    bbl_colum_offset_multypliers = [i for i in reversed(range(len(bbl_col_keys)*2+1)) if i % 2 != 0]
    for offset_multip,  bbl_key in zip(bbl_colum_offset_multypliers, bbl_col_keys):
        p.annular_wedge(0, 0, inner_radius, inner_radius + df[bbl_key] * (outer_radius - inner_radius),
                        -big_angle + angles + offset_multip * small_angle, -big_angle + angles + (offset_multip+1) * small_angle,
                        color=bbl_color[bbl_key])

    # circular axes and lables
    labels = [float(key) for key in percentage_color]

    percentage_series = [0.0, *labels]
    percentage_series = pd.Series(percentage_series)/100
    radii = inner_radius + percentage_series*(outer_radius-inner_radius)
    p.circle(0, 0, radius=radii[1:], fill_color=None, line_color="#282828")
    p.circle(0, 0, radius=radii[0], fill_color=None, line_color="#282828")
    p.text(0, radii[:-1], [str(int(r))+"%" for r in labels],
           text_font_size="9pt", text_align="center", text_baseline="middle")

    # radial axes
    p.annular_wedge(0, 0, inner_radius - 10, outer_radius + 10,
                    -big_angle + angles, -big_angle + angles, color="black")

    # function labels
    xr = outer_radius * np.cos(np.array(-big_angle / 2 + angles))
    yr = outer_radius * np.sin(np.array(-big_angle / 2 + angles))
    label_angle = np.array(-big_angle / 2 + angles)
    label_angle[label_angle < -np.pi / 2] += np.pi  # easier to read labels on the left side
    p.text(xr, yr, df.function_name, angle=label_angle,
           text_font_size="11pt", text_font_style="bold", text_align="center", text_baseline="middle")

    fclx_rect = [-90 + i*20 for i in range(10)]
    fcly_rect = [0]*10

    p.rect(fclx_rect, fcly_rect, width=20, height=15,  color=list(percentage_color.values()))
    p.text([-100, 80], [-20, -20], text=['0%', '100%'], text_font_size='10px', text_align='left', text_baseline='middle')
    heading_text = "Function time" if type == 'time' else "Function executions"
    p.text(-100, 15, text=[heading_text],
           text_font_size="10pt", text_align="left")

    # Basic blocks color labels
    bblx_circle = [outer_radius+60]*len(bbl_color)
    bblx_text = [outer_radius+75]*len(bbl_color)
    bbly = [20*(len(bbl_color)/2) - 20*i for i in range(len(bbl_color))]
    p.rect(bblx_circle, bbly, width=15, height=15,
           color=list(bbl_color.values()))
    p.text(bblx_text, bbly, text=[f'TOP{i+1}' for i in range(len(bbl_color))],
           text_font_size="10pt", text_align="left", text_baseline="middle")

    p.text(outer_radius+45, 20*(len(bbl_color)/2+1)-10, text=["Basic Blocks"],
           text_font_size="10pt", text_align="left")

    heading_text = "Basic block time" if type == 'time' else 'Basic block executions'
    p.text(0, outer_radius+2, text=[heading_text],
           text_font_size="10pt", text_align="center")

    return p

@click.command()
@click.option('--top-functions', '-tf', type=int, default=None,
              help='Limits the functions displayed to specified number to reduce clutter.')
@click.option('--top-basic-blocks', '-tbb', type=int, default=7,
              help='Limits the basic blocks displayed to specified number to reduce clutter.')
@click.option('--sort-by', '-sb', type=str, default='time',
              help='Decide if the top functions/basic blocks should be sorted by execution time (time) or number of executions (execs)')
@pass_profile
def basicblocks(profile: Profile, top_functions: int, top_basic_blocks: int, sort_by: str):

    if sort_by not in ['time', 'execs']:
        # FIXME: exception
        raise Exception("Wrong value of --sort-by option. Choose between 'time' or 'execs'.")

    df_time, df_execs = get_data(profile, top_functions, top_basic_blocks, sort_by)

    output_file("bbl_viz.html", title="Functions and their basic blocks")
    p1 = sunburst(df_time, 'time')
    p2 = sunburst(df_execs, 'execs')

    p = row(p1, p2)
    show(p)