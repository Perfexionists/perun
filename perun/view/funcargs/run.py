""" Scatter plot of dependence of function run--time on values of its arguments
"""

import click
import re

from perun.profile.factory import pass_profile, Profile
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


def extract_function_information(profile: Profile) -> dict:
    """ Extracts information about functions from given profile.

    :param Profile profile: Profile from which to gather the information about functions

    :return dict function_information: relevant information about functions from given profile
    """

    unique_functions = {}

    # merge the collectable data from profile resources
    for _, resource in profile.all_resources(flatten_values=True):  # NOTE: ignoring snapshot number

        if resource['uid'] not in unique_functions and not re.match(r'^BBL#.*#[0-9]+#[0-9]+$', resource['uid']):  
            # first occurrence of the uid that is not a basic block

            function_info = {}
            for key in resource:
                if key in Profile.collectable or re.match(r'^arg_value#[0-9]+', key):
                    # convert the collectable fields to lists
                    function_info[key] = [resource[key]]
                elif re.match(r'^arg_(name|type)#[0-9]+', key):
                    # keep only information about the function 
                    function_info[key] = resource[key]

            unique_functions[resource['uid']] = function_info 

        else:
            # merge collectable data to an existing unique function 
            for key in resource:
                if key in Profile.collectable or re.match(r'^arg_value#[0-9]+', key):
                    unique_functions[resource['uid']][key].append(resource[key])

    return unique_functions


@click.command()
@click.option('--squash', '-s', is_flag=True, default=False,
              help="Squashes all arguments to a single graph.")
@click.option('--function_name', '-fn', type=str, default=None,
              help="Select a function (by its name) which arguments to plot.")
@pass_profile
def funcargs(profile: Profile, squash: bool, function_name: str):
    sns.set(font_scale=1.0)

    function_data = extract_function_information(profile)

    if function_name and function_name not in function_data.keys():
        raise Exception("Wrong function name!")

    # filter functions with arguments only
    for func_name, func_info in function_data.items():
        
        if function_name and func_name != function_name:
            continue  # filters out all functions except the one selected by the user
        
        filter_func = lambda x: re.match(r'^arg_value#[0-9]+', x) and len(func_info[x]) >= 10 
        if not list(filter(filter_func, list(func_info.keys()))):
            continue # filter out functions without arguments and low sample count

        # create dataframe from collectable data 
        func_df = {}
        for key in func_info:
            if re.match(r'^arg_value#[0-9]+', key) or key == 'amount':
                func_df[key] = func_info[key]

        column_keys = list(func_df.keys())
        column_keys.remove('amount')
        func_df = pd.DataFrame(data=func_df)

        subplots_cnt = 1 if squash else len(column_keys)
        fig, axes = plt.subplots(1, subplots_cnt, sharey=True)
        fig.suptitle(func_name)

        if squash:
            for col_name in column_keys:
                a = sns.scatterplot(data=func_df, x=col_name, y='amount')
                #FIXME: should be in for?
                a.set(ylabel='Function run-time [μs]', xlabel='Argument value')

            labels = [] 
            for col_name in column_keys:
                arg_index = col_name.split('#')[1]
                xlabel = f"{func_info['arg_type#'+arg_index]} {func_info['arg_name#'+arg_index]}"
                if 'char *' in xlabel:
                    xlabel += ' (length)'
                labels.append(xlabel)

            plt.legend(labels=labels, title='Arguments legend')

        elif len(column_keys) == 1:
            a = sns.scatterplot(data=func_df, x=column_keys[0], y='amount')
            arg_index = column_keys[0].split('#')[1]
            title = f"{func_info['arg_type#'+arg_index]} {func_info['arg_name#'+arg_index]}"
            xlabel = 'Argument value'
            if 'char *' in title:
                xlabel = 'String length'
            a.set(ylabel='Function run-time [μs]', xlabel=xlabel, title=' '.join(title))

        else:
            for col, col_name in enumerate(column_keys):
                arg_index = col_name.split('#')[1]
                title = f"{func_info['arg_type#'+arg_index]} {func_info['arg_name#'+arg_index]}"
                xlabel = 'Argument value'
                if 'char *' in title:
                    xlabel = 'String length'
                a = sns.scatterplot(ax=axes[col], data=func_df, x=col_name, y="amount")
                a.set(ylabel="Function run-time [μs]", xlabel=xlabel, title=title)

    plt.show()