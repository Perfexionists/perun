"""Tabular view of the profile"""

import click
import tabulate

import perun.profile.convert as convert
from perun.profile.factory import pass_profile


def create_table_from(profile, conversion_function):
    """Using the tabulate package, transforms the profile into table.

    Currently, the represention contains all of the possible keys.

    :param dict profile: profile transformed into the table
    :param function conversion_function: function that converts profile to table
    :return: tabular representation of the profile in string
    """
    dataframe = conversion_function(profile)
    headers = list(dataframe)
    resource_table = dataframe.values.tolist()
    return tabulate.tabulate(resource_table, headers=headers)


@click.group()
@pass_profile
def tableof(_, **__):
    """Textual representation of the profile as a table.

    .. _tabulate: https://pypi.org/project/tabulate/

    \b
      * **Limitations**: `none`.
      * **Interpretation style**: textual
      * **Visualization backend**: tabulate_

    The table is formatted using the tabulate_ library. Currently, we support only the simplest
    form, and allow output to file.

    Refer to :ref:`views-table` for more thorough description and example of
    `table` interpretation possibilities.

    TODO: Enhance documentation
    TODO: Add custom headers
    TODO: Add format
    TODO: Add output to file
    """
    pass


@tableof.command()
@pass_profile
def resources(profile, **_):
    """Outputs the resources of the profile as a table"""
    profile_as_table = create_table_from(profile, convert.resources_to_pandas_dataframe)
    print(profile_as_table)


@tableof.command()
@pass_profile
def models(profile, **_):
    """Outputs the models of the profile as a table"""
    profile_as_table = create_table_from(profile, convert.models_to_pandas_dataframe)
    print(profile_as_table)
