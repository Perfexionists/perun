"""Tabular view of the profile"""

import click
import tabulate

import perun.profile.convert as convert
from perun.profile.factory import pass_profile


def create_table_from(profile):
    """Using the tabulate package, transforms the profile into table.

    Currently, the represention contains all of the possible keys.

    :param dict profile: profile transformed into the table
    :return: tabular representation of the profile in string
    """
    dataframe = convert.resources_to_pandas_dataframe(profile)
    headers = list(dataframe)
    resource_table = dataframe.values.tolist()
    return tabulate.tabulate(resource_table, headers=headers)


@click.command()
@pass_profile
def table(profile, **kwargs):
    """Textual representation of the resources as a table.

    Table shows resources in classical tabular format.

    .. _tabulate: https://pypi.org/project/tabulate/

    \b
      * **Limitations**: `none`.
      * **Interpretation style**: textual
      * **Visualization backend**: tabulate_

    The table is formated using the tabulate_ library. Currently, we support only the simplest form,
    and allow output to file.

    Refer to :ref:`views-table` for more thorough description and example of
    `table` interpretation possibilities.

    TODO: Enhance documentation
    TODO: Add custom headers
    TODO: Add format
    TODO: Add output to file
    """
    profile_as_table = create_table_from(profile)
    print(profile_as_table)
