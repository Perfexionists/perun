
import os
import click
import tabulate

import perun.profile.convert as convert
import perun.profile.query as query
import perun.profile.helpers as profiles


def output_table_to(table, target, target_file):
    """Outputs the table either to stdout or file

    :param str table: outputted table
    :param str target: either file or stdout
    :param str target_file: name of the output file
    """
    if target == 'file':
        with open(target_file, 'w') as wtf:
            wtf.write(table)
    else:
        print(table)


def create_table_from(profile, conversion_function, headers, tablefmt):
    """Using the tabulate package, transforms the profile into table.

    Currently, the representation contains all of the possible keys.

    :param dict profile: profile transformed into the table
    :param function conversion_function: function that converts profile to table
    :param list headers: list of headers of the table
    :param str tablefmt: format of the table
    :return: tabular representation of the profile in string
    """
    dataframe = conversion_function(profile)
    resource_table = dataframe[headers].values.tolist()
    return tabulate.tabulate(resource_table, headers=headers, tablefmt=tablefmt)


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


def process_output_file(ctx, _, value):
    """Generates the name of the output file, if no value is issued

    If no output file is set, then we generate the profile name according to the profile
    and append the "resources_of" or "models_of" prefix to the file.

    :param click.Context ctx: context of the called command
    :param click.Option _: called option
    :param str value: output file of the show
    :return: output file of the show
    """
    if value:
        return value
    else:
        prof_name = profiles.generate_profile_name(ctx.parent.params['profile'])
        return ctx.command.name + "_of_" + os.path.splitext(prof_name)[0]


@click.group()
@click.option('--to-file', '-tf', 'output_to', flag_value='file',
              help='The table will be saved into a file. By default, the name of the output file'
                   ' is automatically generated, unless `--output-file` option does not specify'
                   ' the name of the output file.', default=True)
@click.option('--to-stdout', '-ts', 'output_to', flag_value='stdout',
              help='The table will be output to standard output.')
@click.option('--output-file', '-of', default=None, callback=process_output_file,
              help='Target output file, where the transformed table will be saved.')
@click.option('--format', '-f', 'tablefmt', default='simple',
              type=click.Choice(tabulate.tabulate_formats),
              help='Format of the outputted table')
@click.pass_context
def tableof(*_, **__):
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
    tablefmt = ctx.parent.params['tablefmt']
    profile = ctx.parent.parent.params['profile']
    profile_as_table = create_table_from(
        profile, convert.resources_to_pandas_dataframe, headers, tablefmt
    )
    output_table_to(
        profile_as_table, ctx.parent.params['output_to'], ctx.parent.params['output_file']
    )


@tableof.command()
@click.pass_context
@click.option('--headers', '-h', default=None, multiple=True,
              metavar="<key>", callback=process_headers,
              help="Sets the headers that will be displayed in the table. If none are stated "
                   "then all of the headers will be outputed")
def models(ctx, headers, **_):
    """Outputs the models of the profile as a table"""
    tablefmt = ctx.parent.params['tablefmt']
    profile = ctx.parent.parent.params['profile']
    profile_as_table = create_table_from(
        profile, convert.models_to_pandas_dataframe, headers, tablefmt
    )
    output_table_to(
        profile_as_table, ctx.parent.params['output_to'], ctx.parent.params['output_file']
    )
