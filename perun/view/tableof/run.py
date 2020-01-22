
import click
import tabulate

import perun.profile.convert as convert
import perun.profile.query as query


def create_table_from(profile, conversion_function, headers):
    """Using the tabulate package, transforms the profile into table.

    Currently, the representation contains all of the possible keys.

    :param dict profile: profile transformed into the table
    :param function conversion_function: function that converts profile to table
    :param list headers: list of headers of the table
    :return: tabular representation of the profile in string
    """
    dataframe = conversion_function(profile)
    resource_table = dataframe[headers].values.tolist()
    return tabulate.tabulate(resource_table, headers=headers)


def process_headers(ctx, option, value):
    """Processes list of headers of the outputted table

    :param click.Context ctx: context of the called command
    :param click.Option option: called option
    :param tuple value: tuple of stated header keys
    :return: list of headers of the table
    """
    headers = []
    if ctx.command.name == 'resources':
        headers = list(query.all_resource_fields_of(ctx.parent.parent.params['profile'])) \
                  + ['snapshots']
    elif ctx.command.name == 'models':
        headers = list(query.all_model_fields_of(ctx.parent.parent.params['profile']))

    # In case something was stated in the CLI we use these headers
    if value:
        for val in value:
            if val not in headers:
                raise click.BadOptionUsage(
                    option, "invalid choice for table header: {} (choose from {})".format(
                        val, ", ".join(headers)
                    )
                )
        else:
            return list(value)
    # Else we output everything
    else:
        return sorted(headers)


@click.group()
@click.pass_context
def tableof(ctx, **kwargs):
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
    TODO: Add format
    TODO: Add output to file
    """
    pass


@tableof.command()
@click.option('--headers', '-h', default=None, multiple=True,
              metavar="<key>", callback=process_headers,
              help="Sets the headers that will be displayed in the table. If none are stated "
                   "then all of the headers will be outputed")
@click.pass_context
def resources(ctx, headers, **_):
    """Outputs the resources of the profile as a table"""
    profile = ctx.parent.parent.params['profile']
    profile_as_table = create_table_from(profile, convert.resources_to_pandas_dataframe, headers)
    print(profile_as_table)


@tableof.command()
@click.pass_context
@click.option('--headers', '-h', default=None, multiple=True,
              metavar="<key>", callback=process_headers,
              help="Sets the headers that will be displayed in the table. If none are stated "
                   "then all of the headers will be outputed")
def models(ctx, headers, **_):
    """Outputs the models of the profile as a table"""
    profile = ctx.parent.parent.params['profile']
    profile_as_table = create_table_from(profile, convert.models_to_pandas_dataframe, headers)
    print(profile_as_table)
