""" Tree map of function calls
"""
from pprint import pprint
from typing import List

import click
import os

from perun.profile.factory import pass_profile, Profile
from perun.profile.convert import resources_to_pandas_dataframe
import pandas as pd
import plotly.graph_objects as go


def extract_function_information(profile: Profile) -> pd.DataFrame:
    unique_functions = {}

    # merge the collectable data from profile resources
    for _, resource in profile.all_resources(flatten_values=True):  # NOTE: ignoring snapshot number
        # Uniqueness of a function depends on its name and the caller
        unique_function_key = resource['uid'] + '#' + resource['caller']
        if unique_function_key not in unique_functions:
            # first occurrence of the uid with the specific caller that is not a basic block
            unique_functions[unique_function_key] = {'uid': resource['uid'],
                                                     'caller': resource['caller'],
                                                     'amount': resource['amount']}
        else:
            unique_functions[unique_function_key]['amount'] += resource['amount']
    return pd.DataFrame(unique_functions)


def aggregate_files(locations: pd.Series):
    if locations.drop_duplicates().size > 1:
        raise Exception("Provided profile is inconsistent.")
    return locations.iloc[0]

def aggregate_lines(lines: pd.Series):
    print(lines)
    lines.drop_duplicates()
    print(lines)
    if lines.drop_duplicates().size > 1:
        raise Exception("Provided profile is inconsistent.")
    return lines.iloc[0] if isinstance(lines.iloc[0], str) else str(lines.iloc[0])

def get_file_contents_by_range(file: str, start: int, end: int) -> str:
    if not os.path.isfile(file):
        return ""
    if start > end:
        start, end = end, start

    with open(file, "r") as file_handle:
        contents = file_handle.read().split('\n')[start - 1:end - 1 + 1]
    return '\n'.join(contents)


def get_file_contents_by_sequence(file: str, lines_sequence: List[int]) -> str:
    if not os.path.isfile(file):
        return ""

    with open(file, "r") as file_handle:
        file: List[str] = file_handle.read().split('\n')
        contents: List[str] = []
        for line_number in lines_sequence:
            contents.append(f"{line_number}: " + file[line_number-1])
    return '\n'.join(contents)


@click.command()
@click.option('--depth', '-d', type=int, default=-1,
              help="Number of levels initially displayed.")
@click.option('--graph-type', '-t', type=str, default='treemap',
              help="Select a type of the visualization ['treemap', 'icicle', 'sunburst'].")
@click.option('--basic-blocks', '-b', is_flag=True, default=False,
              help="Includes basic blocks if they are available in the specified profile.")
@pass_profile
def treemap(profile: Profile, depth: str, graph_type: int, basic_blocks: bool):
    df = resources_to_pandas_dataframe(profile)
    df = df.drop(columns=['timestamp', 'time', 'snapshots', 'subtype', 'type', 'workload'])
    # pd.set_option('display.max_columns', None)
    # df.to_csv('out.csv')

    # Override basic blocks flag if expected values are not found in the dataframe
    if basic_blocks and 'instructions-count' not in df.columns:
        # TODO: add warning
        basic_blocks = False


    # Form aggregation dictionary
    aggregation = {'amount': 'sum',
                   'source-lines': aggregate_lines,
                   'source-file': aggregate_files}


    amounts = df.groupby(['uid', 'caller']).aggregate(aggregation).reset_index()

    # Filter out the basic blocks if present and should not be displayed
    if not basic_blocks and 'instructions-count' in df.columns:
        for idx, row in amounts.iterrows():
            if row['uid'].startswith("BBL#"):
                amounts.drop(idx, inplace=True)



    # Print expected time vs accumulated time
    for _, row in amounts.iterrows():
        expected_sum = row['amount']
        accumulated_sum = 0
        for i, nr in amounts.iterrows():
            if nr['caller'] == f"{row['uid']}{'#' if row['caller'] else ''}{row['caller']}":
                accumulated_sum += nr['amount']
                if nr['amount'] > row['amount']:
                    amounts.at[i, 'amount'] = row['amount']
        #print(row['uid'], expected_sum, accumulated_sum)

    with pd.option_context('display.max_rows', None):
        print('-----------------------------------')
        print(amounts)

    parents = list(amounts['caller'])
    labels = list(amounts['uid'])
    ids = list(map(lambda x: f"{x[1]}{'#' if x[0] else ''}{x[0]}", zip(parents, labels)))

    viz_method_map = {'treemap': go.Treemap,
                      'icicle': go.Icicle,
                      'sunburst': go.Sunburst}

    # get code corresponding to each basic block and add it as a column to the amounts dataframe
    if basic_blocks:
        #print(f"\n{'function name' :<20}{'BBL' :^5}{'start' :^7}{'end' :^7}{'runtime':^12}{'lines' :<100}")
        code_col = []
        for _, row in amounts.iterrows():
            if not row['uid'].startswith('BBL#'):
                code_col.append("")
                continue

            lines: int | str = row['source-lines']
            lines_sequence: List[int] = []
            if isinstance(lines, int):
                lines_sequence = [lines]
            elif isinstance(lines, str) and lines:
                lines_sequence = [int(i) for i in lines.split(',')]

            contents = get_file_contents_by_sequence(row['source-file'], lines_sequence)
            #print(f"{row['uid'] :<20}{0:^5}{row['source-line']:^7}{row['source-line-end']:^7}{row['amount']:^12}{contents:<100}")
            contents = '\n' + contents + '\n'
            code_col.append(contents.replace('\n', '<br>'))

        amounts['code'] = code_col
        # with pd.option_context('display.max_rows', None):
        #     print(amounts)


    fig = go.Figure(viz_method_map[graph_type](
        branchvalues='total',
        labels=labels,
        parents=parents,
        ids=ids,
        values=list(amounts['amount']),
        maxdepth=depth,
        textinfo='label+percent root+percent parent+text',
        hoverinfo='label+text',
        marker_colorscale='RdBu'
    ))

    hover_texts = []
    for _, row in amounts.iterrows():
        formated_time = f"{row['amount']:,} μs".replace(',', ' ')
        hover_text = f"File: {row['source-file']} <br>" \
                     f"Lines: {row['source-lines']} <br>" \
                     f"Time: {formated_time}<br>"
        hover_texts.append(hover_text)
    amounts['hover'] = hover_texts

    fig.update_traces(hovertext=amounts['hover'])

    if graph_type == 'icicle':
        fig.update_traces(tiling=dict(orientation='v', flip='y'))
    if graph_type == 'treemap':
        fig.update_traces(marker=dict(cornerradius=5))
    if basic_blocks:
        fig.update_traces(text=amounts['code'])
    fig.update_layout(margin=dict(t=50, l=25, r=25, b=25))
    fig.show()
    fig.write_html('functions_runtime_viz.html')
