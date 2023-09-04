"""Sunburst graph representing the basic blocks and function run-times along with execution counts.
"""

import click
import os
from perun.profile.factory import pass_profile, Profile
import perun.profile.convert as convert
from perun.utils.log import msg_to_stdout
import bokeh.palettes as palettes
from bokeh.plotting import figure, save, output_file
from bokeh.layouts import row,column
from bisect import insort, bisect
import numpy as np
import pandas as pd
from typing import Union, List


class BasicBlockData:

    def __init__(self, time: int, execs: int, line_start: int, line_end: int, file: str):
        self.time = time
        self.execs = execs 
        self.src_line_start = line_start
        self.src_line_end = line_end
        self.src_file = file

        self.runtime_percentage = 0
        self.execs_percentage = 0

    def __repr__(self):
        return (f'\n\t\t\ttime: {self.time}, execs: {self.execs}'
                f'\n\t\t\truntime_percentage: {self.runtime_percentage}'
                f'\n\t\t\texecs_percentage: {self.execs_percentage}'
                f'\n\t\t\tlocation: {self.src_line_start}-{self.src_line_end} in {self.src_file}')

class FunctionData:

    def __init__(self, name: str, time: int = 0, execs: int = 0, bbls: List[BasicBlockData] = []):
        self.name = name
        self.time = time
        self.execs = execs 
        self.bbls = bbls 

        # time spent exclusively in the function calculated from basic block time
        self.exclusive_time = 0 

        # percentage group of the function that discloses the time spent in the function compared to other functions
        self.function_time_percentage_group = 0
        self.function_execs_percentage_group = 0
    
    def sort_bbls(self, sort_by: str='time'):
        self.bbls = sorted(self.bbls, key=lambda bbl: bbl.time if sort_by == 'time' else bbl.execs, reverse=True)
    
    def __repr__(self):
        bbls = ','.join([f'\n\t\ttop{i}: {bbl}'for i,bbl in enumerate(self.bbls)])
        return (f'Function {self.name}:'
                f'\n\ttime: {self.time}, exclusive: {self.exclusive_time}'
                f'\n\texecs: {self.execs}'
                f'\n\ttime_percentage_group: {self.function_time_percentage_group}, execs_percentage_group: {self.function_execs_percentage_group}'
                f'\n\tbbls: {bbls}')


def convert_to_internal_repr(data: pd.DataFrame):

    function_data_frame = data[~data['uid'].str.match(r'^BBL#.*#[0-9]+')]
    function_names = function_data_frame.uid.unique()

    functions_data = []
    for func_name in function_names:

        # How much time was spent in function and how many times was it called
        func_time_deltas = function_data_frame[function_data_frame['uid'] == func_name].amount.values
        func_time = sum(func_time_deltas)
        func_execs = len(func_time_deltas)
        func = FunctionData(func_name, func_time, func_execs)
        # How much time was spent in functions basic blocks and how many times were they executed
        func_bbls_data_frame = data[data['uid'].str.match(f'^BBL#{func_name}#[0-9]+')]
        bbl_names = func_bbls_data_frame.uid.unique()
        bbls = []
        for bbl_name in bbl_names:
            bbl_data = func_bbls_data_frame[func_bbls_data_frame['uid'] == bbl_name]
            bbl_time_deltas = bbl_data.amount.values
            bbl_time = sum(bbl_time_deltas)
            bbl_execs = len(bbl_time_deltas)
            bbl_src_line_start = int(bbl_data.source_line.values[0]) if len(bbl_data.source_line.values) > 0 else 0
            bbl_src_line_end = int(bbl_data.source_line_end.values[0]) if len(bbl_data.source_line_end.values) > 0 else 0
            bbl_src_file = bbl_data.source_file.values[0] if len(bbl_data.source_file.values) > 0 else ""

            bbl = BasicBlockData(bbl_time, bbl_execs, bbl_src_line_start, bbl_src_line_end, bbl_src_file)
            bbls.append(bbl)

        func.bbls = bbls
        # exclusively spent time in the function without other function calls inside
        func.exclusive_time = sum([bbl.time for bbl in func.bbls])
        functions_data.append(func)

    return functions_data


def extract_relevant_data_to_internal_representation(profile: Profile, top_functions: int, top_basic_blocks: int, sort_by: str):

    data = convert.resources_to_pandas_dataframe(profile)

    # drop unnecessary columns
    data.drop(columns=['type', 'subtype', 'time', 'workload', 'tid', 'snapshots'], inplace=True, axis=1)

    if data.loc[data['uid'] == 'main'].empty:
        # FIXME: exception
        raise Exception("Couldn't create graphs, not enough data. Profile doesn't include main function.")

    # get start and duration of main functions for data filtering
    main_start = data.loc[data['uid'] == 'main'].timestamp.values[0]
    main_duration = data.loc[data['uid'] == 'main'].amount.values[0]
    main_end = main_start + main_duration

    # filter functions executed before and after main
    data = data[(data['timestamp'] >= main_start) & (data['timestamp']+data['amount'] <= main_end)]

    function_data = convert_to_internal_repr(data)

    # Sort the functions as well as their basic blocks and limit them to given amount of top functions and basic blocks
    # NOTE: functions are sorted by exclusive time since it is used in the visualization instead of time 
    function_data = function_data[:top_functions]
    function_data = sorted(function_data, key=lambda func: func.exclusive_time if sort_by == 'time' else func.execs)
    all_functions_exclusive_times_sum = sum([function.exclusive_time for function in function_data]) 
    all_functions_executions_sum = sum([function.execs for function in function_data]) 
    for function in function_data:
        function.sort_bbls(sort_by)
        function.bbls = function.bbls[:top_basic_blocks]
        
        # fill the missing basic blocks with dummy objects
        # NOTE: This is needed due to the character of sunburst graph creation which requires equal amount of basic
        # blocks in every function.
        # FIXME instead of comparing to given cap, count the max bbls there are after truncation and fill towards that instead
        while len(function.bbls) < top_basic_blocks:
            function.bbls.append(BasicBlockData(time=0, execs=0, line_start=0, line_end=0, file=""))

        basic_block_executions_sum = sum([bbl.execs for bbl in function.bbls])
        for bbl in function.bbls:
            runtime_percentage = bbl.time / function.exclusive_time
            execs_percentage = bbl.execs / basic_block_executions_sum
            # NOTE: scaling down to remain in given scope, because the collected data can be bit off
            bbl.runtime_percentage = runtime_percentage if runtime_percentage < 1.0 else 1.0
            bbl.execs_percentage = execs_percentage if execs_percentage < 1.0 else 1.0

        function.function_time_percentage_group = function.exclusive_time/all_functions_exclusive_times_sum*100 
        function.function_execs_percentage_group = function.execs/all_functions_executions_sum*100
        
    #import pprint
    #pprint.pprint(function_data)
    return function_data


def create_sunburst_graph(function_data, type='time'):

    # Create color palettes
    num_of_bbls = len(function_data[0].bbls)
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

    big_angle = 2.0 * np.pi / (len(function_data) + 1)  # +1 for the annotations column
    small_angle = big_angle / (num_of_bbls*2+1)

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
    angles = np.pi / 2 - big_angle / 2 - np.array(range(0,len(function_data))) * big_angle
    colors = []
    func_percentage_groups = [function.function_time_percentage_group if type == 'time' else function.function_execs_percentage_group for function in function_data]
    for func_percentage_group in func_percentage_groups:
        percentage_group = (func_percentage_group//10+1)*10
        colors.append(percentage_color[str(int(percentage_group))])
    p.annular_wedge(0, 0, inner_radius, outer_radius, -big_angle + angles, angles, color=colors)

    # small wedges
    bbl_colum_offset_multypliers = [i for i in reversed(range(num_of_bbls*2+1)) if i % 2 != 0]
    for bbl_idx, offset_multip,in enumerate(bbl_colum_offset_multypliers):
        length = inner_radius + np.array([function.bbls[bbl_idx].runtime_percentage if type == 'time' else function.bbls[bbl_idx].execs_percentage for function in function_data]) * (outer_radius - inner_radius)
        p.annular_wedge(0, 0, inner_radius, length,
                        -big_angle + angles + offset_multip * small_angle, -big_angle + angles + (offset_multip+1) * small_angle,
                        color=bbl_pallete[bbl_idx])

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
    p.text(xr, yr, np.array([function.name for function in function_data]), angle=label_angle,
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


    # Basic blocks mapping
    from bokeh.models import ColumnDataSource, TableColumn, DataTable

    table_data = {'function_names': [], 'source_files': []}
    for function in reversed(function_data):
        table_data['function_names'].append(function.name)
        for bbl_idx, bbl in enumerate(function.bbls):
            key = f'top_{bbl_idx+1}_bbls'
            if key not in table_data.keys():
                table_data[key] = [] 

            location = f'{bbl.src_line_start}-{bbl.src_line_end}'
            if bbl.src_line_start == 0 and bbl.src_line_end == 0:
                location = f'Not a BBL'
                
            table_data[key].append(location)
        table_data['source_files'].append(function.bbls[0].src_file)

    table_data = pd.DataFrame(table_data)

    source = ColumnDataSource(table_data)
    columns = []
    columns.append(TableColumn(field='function_names', title='Function name'))
    for bbl_num in range(1, num_of_bbls): 
        columns.append(TableColumn(field=f'top_{bbl_num}_bbls', title= f'TOP{bbl_num} BBL'))
    columns.append(TableColumn(field='source_files', title='Source file path', width=1000))

    my_table = DataTable(source=source, columns=columns, fit_columns=True, width=1950, height=27*(len(function_data)+1))

    return p, my_table










# def get_functions_data(data: pd.DataFrame, top_basic_blocks: Union[int, None]=None, sort_by :str='time') -> dict:
#     """Converts data from dataframe into records about functions instead and filters basic blocks.

#     :param DataFrame data: data from which to create function information
#     :param int top_basic_blocks: select how many top basic blocks to filter (optional)
#     :param string sort_by: select sorting method time/execs

#     :returns dict new_data: dictionary representation of filtered data
#     """

#     function_data = data[~data['uid'].str.match(r'^BBL#.*#[0-9]+')]
#     function_names = function_data.uid.unique()

#     new_data = {}
#     for function_name in function_names:

#         # How much time was spent in function and how many times was it called
#         func_time_deltas = function_data[function_data['uid'] == function_name].amount.values
#         new_data[function_name] = {'func_time': sum(func_time_deltas), 'func_execs': len(func_time_deltas),
#                                    'bbl_times': [], 'bbl_execs': []}

#         # How much time was spent in functions basic blocks and how many times were they executed
#         func_bbls = data[data['uid'].str.match(f'^BBL#{function_name}#[0-9]+')]
#         bbl_names = func_bbls.uid.unique()
#         for bbl_name in bbl_names:
#             bbl_data = func_bbls[func_bbls['uid'] == bbl_name]
#             time_deltas = bbl_data.amount.values
#             if sort_by == 'execs':
#                 insertion_idx = bisect(new_data[function_name]['bbl_execs'], sum(time_deltas))
#                 insort(new_data[function_name]['bbl_execs'], sum(time_deltas))
#                 new_data[function_name]['bbl_times'].insert(insertion_idx, len(time_deltas))
#             else:
#                 insertion_idx = bisect(new_data[function_name]['bbl_times'], sum(time_deltas))
#                 insort(new_data[function_name]['bbl_times'], sum(time_deltas))
#                 new_data[function_name]['bbl_execs'].insert(insertion_idx, len(time_deltas))

#         # overwrite the time of function with exclusively spent time in the function without other function calls inside
#         new_data[function_name]['func_time'] = sum(new_data[function_name]['bbl_times'])

#         if top_basic_blocks:
#             new_data[function_name]['bbl_times'] = new_data[function_name]['bbl_times'][:top_basic_blocks]
#             new_data[function_name]['bbl_execs'] = new_data[function_name]['bbl_execs'][:top_basic_blocks]

#     import pprint 
#     pprint.pprint(new_data)
#     return new_data


# def get_data(profile: Profile, top_functions: int, top_basic_blocks: int, sort_by: str) -> pd.DataFrame:
#     """Prepares data for sunburst plot and returns them as dataframes.

#     :param Profile  profile: profile from which to extract data
#     :param int top_functions: select how many top functions to include in data
#     :param int top_basic_blocks: select how many top basic blocks to include in data
#     :param string sort_by: select method of sorting time/execs

#     :returns DataFrame, DataFrame dataframes: dataframes containing the filtered data for two different sunbursts
#     """

#     data = convert.resources_to_pandas_dataframe(profile)

#     # drop unnecessary coumns
#     data.drop(columns=['type', 'subtype', 'time', 'workload', 'tid', 'snapshots'], inplace=True, axis=1)

#     # get start and duration of main functions for data filtering
#     if data.loc[data['uid'] == 'main'].empty:
#         # FIXME: exception
#         raise Exception("Couldn't create graphs, not enough data. Profile doesn't include main function.")

#     main_start = data.loc[data['uid'] == 'main'].timestamp.values[0]
#     main_duration = data.loc[data['uid'] == 'main'].amount.values[0]
#     main_end = main_start + main_duration

#     # filter functions executed before and after main
#     data = data[(data['timestamp'] >= main_start) & (data['timestamp']+data['amount'] <= main_end)]

#     functions_data = get_functions_data(data, top_basic_blocks, sort_by)

#     functions_data_sorted_keys = sorted(functions_data, key=lambda a: functions_data[a][f'func_{sort_by}'], reverse=True)

#     df_time = create_df_from_functions_data(functions_data, time=True, main_duration=main_duration)
#     df_execs = create_df_from_functions_data(functions_data)

#     # apply the sort to dataframes
#     df_time = df_time.set_index('function_name').loc[functions_data_sorted_keys].reset_index()
#     df_execs = df_execs.set_index('function_name').loc[functions_data_sorted_keys].reset_index()

#     if top_functions:
#         df_time = df_time[:top_functions]
#         df_execs = df_execs[:top_functions]

#     # convert the values in func_percentage_group columns after filtering to actual percentages
#     for df in [df_time, df_execs]:
#         sum_of_col_values = df.func_percentage_group.sum()
#         for i, row in df.iterrows():
#             df.loc[i, 'func_percentage_group'] = (row['func_percentage_group']/sum_of_col_values)*100

#     return df_time, df_execs


# def create_df_from_functions_data(functions_data :dict, time :bool=False, main_duration :Union[int,None]=None) -> pd.DataFrame:
#     """ Converts the function data into a data frame format suitable for sunburst plot

#     :param dict functions_data: dict containing filtered information about functions
#     :param bool time: flag that decides what df is being created time/execs
#     :param int main_duration: selects the main duration from which are the percentages calculated

#     :returns DataFrame df: dataframe with data about functions provided
#     """
#     # unify counts of basic blocks with zeroes so that dataframe creation is possible
#     max_bbls = 0
#     all_func_execs = 0
#     for func_data in functions_data.values():
#         # find out what is the max number of basic blocks
#         current_bbls_cnt = len(func_data['bbl_times'])
#         max_bbls = current_bbls_cnt if current_bbls_cnt > max_bbls else max_bbls
#         # and also the number of function calls
#         all_func_execs += func_data['func_execs']

#     # fill the missing values with dummy zeroes
#     for func_data in functions_data.values():
#         while len(func_data['bbl_times']) < max_bbls:
#             func_data['bbl_times'].append(0)
#             func_data['bbl_execs'].append(0)

#     data_frame = {'function_name': [], 'func_percentage_group': []}

#     for i in range(max_bbls):
#         data_frame[f'BBL{i + 1}'] = []

#     for func_name, func_data in functions_data.items():

#         # function_name
#         data_frame['function_name'].append(func_name)

#         # function_percentage_group
#         if time and main_duration:
#             #data_frame['func_percentage_group'].append((func_data[f'func_time'] / main_duration) * 100)
#             # Store func time in this column and edit it when the size of dataframe is filtered
#             # determines the percentage group from the sum of this column after the filtering
#             data_frame['func_percentage_group'].append(func_data[f'func_time'])
#             function_exclusive_time = sum(func_data['bbl_times'])  # time spent exclusively in the function
#             for idx, bbl_run_time in enumerate(func_data['bbl_times']):
#                 # bbl_run_time - each run time of this basic block combined
#                 exclusive_bbl_runtime_percentage = bbl_run_time / function_exclusive_time
#                 data_frame[f'BBL{idx + 1}'].append(exclusive_bbl_runtime_percentage if exclusive_bbl_runtime_percentage <= 1.0 else 1.0)
#         else:
#             #data_frame['func_percentage_group'].append((func_data['func_execs'] / all_func_execs) * 100)
#             # Store func execs in this column and edit it when the size of dataframe is filtered
#             # determines the percentage group from the sum of this column after the filtering
#             data_frame['func_percentage_group'].append(func_data['func_execs'])
#             basic_block_executions_sum = sum(func_data['bbl_execs'])  # number of executions of basic blocks in the function
#             for idx, bbl_exec_cnt in enumerate(func_data['bbl_execs']):
#                 bbl_execution_percentage = bbl_exec_cnt / basic_block_executions_sum
#                 data_frame[f'BBL{idx + 1}'].append(bbl_execution_percentage if bbl_execution_percentage <= 1.0 else 1.0)

#     return pd.DataFrame(data_frame)


# def sunburst(df:pd.DataFrame, type :str='time'):
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

    output_file("bbl_viz.html", title="Functions and their basic blocks")

    data = extract_relevant_data_to_internal_representation(profile, top_functions, top_basic_blocks, sort_by)
    p1, table1 = create_sunburst_graph(data, 'time')
    p2, table2 = create_sunburst_graph(data, 'execs')

    p = column(row(p1, p2), table1, table2)

    # df_time, df_execs = get_data(profile, top_functions, top_basic_blocks, sort_by)
    # p1 = sunburst(df_time, 'time')
    # p2 = sunburst(df_execs, 'execs')
    #p = row(p1, p2)
    save(p)


    for function in data:
        print(f"\n{'function name' :<20}{'BBL' :^5}{'start' :^7}{'end' :^7}{'runtime%' :^10}{'runtime':^12}{'lines' :<100}")
        for idx,bbl in enumerate(function.bbls):
            if not os.path.isfile(bbl.src_file):
                continue
            with open(bbl.src_file, "r") as bbl_src_file_handle:
                bbl_src_file = bbl_src_file_handle.read()
                bbl_src_file = bbl_src_file.split('\n')
                bbl_src_line_start = bbl.src_line_start-1
                bbl_src_line_end = bbl.src_line_end-1
                if bbl_src_line_end < bbl_src_line_start:
                    bbl_src_line_start, bbl_src_line_end = bbl_src_line_end, bbl_src_line_start
                bbl_runtime_percentage_formated = f"{bbl.runtime_percentage*100:.2f}"
                print(f"{function.name :<20}{idx:^5}{bbl.src_line_start:^7}{bbl.src_line_end:^7}{bbl_runtime_percentage_formated:^10}{bbl.time:^12}{str(bbl_src_file[bbl_src_line_start:bbl_src_line_end+1]):<100}")