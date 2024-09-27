""" Scatter plot of dependence of function run--time on values of its arguments
"""

from typing import Union, Dict, List, Any, Optional

import click
import re

from perun.profile.factory import pass_profile, Profile
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

ProfileEntryFunctionInfo = Dict[str, Union[str, int, float, List[Any]]]


def extract_function_information(profile: Profile) -> Dict[str, ProfileEntryFunctionInfo]:
    """Extracts information about functions from given profile.

    :param Profile profile: Profile from which to gather the information about functions

    :return dict function_information: relevant information about functions from given profile
    """
    unique_functions: Dict[str, ProfileEntryFunctionInfo] = {}

    # merge the collectable data from profile resources
    for _, resource in profile.all_resources(flatten_values=True):  # NOTE: ignoring snapshot number
        is_first_occurrence: bool = resource["uid"] not in unique_functions
        is_function: bool = re.match(r"^BBL#.*#[0-9]+#[0-9]+$", resource["uid"]) is None
        if is_first_occurrence and is_function:
            # first occurrence of the uid that is not a basic block
            function_info: ProfileEntryFunctionInfo = {}
            for key in resource:
                if key in Profile.collectable or re.match(r"^arg_value#[0-9]+", key):
                    # convert the collectable fields to lists - initializes the list for the
                    # first occurrence
                    function_info[key] = [resource[key]]
                elif re.match(r"^arg_(name|type)#[0-9]+", key):
                    # keep only information about the function
                    function_info[key] = resource[key]
            unique_functions[resource["uid"]] = function_info
        else:
            # merge collectable data to an existing unique function
            for key in resource:
                if key in Profile.collectable or re.match(r"^arg_value#[0-9]+", key):
                    unique_functions[resource["uid"]][key].append(resource[key])
    return unique_functions


@click.command()
@click.option(
    "--squash", "-s", is_flag=True, default=False, help="Squashes all arguments to a single graph."
)
@click.option(
    "--function_name",
    "-fn",
    type=str,
    default=None,
    help="Select a function (by its name) which arguments to plot.",
)
@pass_profile
def funcargs(profile: Profile, squash: bool, function_name: Optional[str]) -> None:
    sns.set(font_scale=1.0)
    function_data: Dict[str, ProfileEntryFunctionInfo] = extract_function_information(profile)

    if function_name and function_name not in function_data.keys():
        # TODO: exception
        raise Exception("Wrong function name!")

    # filter functions with arguments only
    for func_name, func_info in function_data.items():

        if function_name and func_name != function_name:
            continue  # filters out all functions except the one selected by the user

        # filter out function without arguments and low sample count
        if not list(
            filter(
                lambda x: (re.match(r"^arg_value#[0-9]+", x) and len(func_info[x]) >= 10),
                list(func_info.keys()),
            )
        ):
            continue

        # create dataframe from collectable data
        func_data: ProfileEntryFunctionInfo = {}
        for key in func_info:
            if re.match(r"^arg_value#[0-9]+", key) or key == "amount":
                func_data[key] = func_info[key]

        column_keys: List[str] = list(func_data.keys())
        column_keys.remove("amount")
        func_df: pd.DataFrame = pd.DataFrame(data=func_data)

        subplots_cnt: int = 1 if squash else len(column_keys)
        fig, axes = plt.subplots(1, subplots_cnt, sharey=True)
        fig.suptitle(func_name)

        if squash:
            for col_name in column_keys:
                a = sns.scatterplot(data=func_df, x=col_name, y="amount")
                a.set(ylabel="Function run-time [μs]", xlabel="Argument value")

            labels: List[str] = []
            for col_name in column_keys:
                arg_index: str = col_name.split("#")[1]
                arg_type: str = func_info[f"arg_type#{arg_index}"]
                arg_name: str = func_info[f"arg_name#{arg_index}"]
                x_label: str = f"{arg_type} {arg_name}"
                if "char *" in x_label:
                    x_label += " (length)"
                labels.append(x_label)

            plt.legend(labels=labels, title="Arguments legend")

        elif len(column_keys) == 1:
            a = sns.scatterplot(data=func_df, x=column_keys[0], y="amount")
            arg_index: str = column_keys[0].split("#")[1]
            arg_type: str = func_info[f"arg_type#{arg_index}"]
            arg_name: str = func_info[f"arg_name#{arg_index}"]
            title: str = f"{arg_type} {arg_name}"
            x_label: str = "Argument value"
            if "char *" in title:
                x_label = "String length"
            a.set(ylabel="Function run-time [μs]", xlabel=x_label, title=" ".join(title))
        else:
            for col, col_name in enumerate(column_keys):
                arg_index: str = col_name.split("#")[1]
                arg_type: str = func_info[f"arg_type#{arg_index}"]
                arg_name: str = func_info[f"arg_name#{arg_index}"]
                title: str = f"{arg_type} {arg_name}"
                x_label: str = "Argument value"
                if "char *" in title:
                    x_label: str = "String length"
                a = sns.scatterplot(ax=axes[col], data=func_df, x=col_name, y="amount")
                a.set(ylabel="Function run-time [μs]", xlabel=x_label, title=title)

    plt.show()
