"""Set of helper functions for working with command line.

Contains functions for click api, for processing parameters from command line, validating keys,
and returning default values.
"""

import click

import perun.logic.config as config
import perun.profile.query as query
import perun.utils.log as log

__author__ = 'Tomas Fiedor'


def process_config_option(_, param, value):
    """Processes the value of the param and stores it in the temporary config

    :param click.Context _: unused click context
    :param click.Option param: click option, that is being processed
    :param object value: value we are setting
    :return: set value
    """
    option_name = param.human_readable_name.replace("__", ".")
    if value:
        config.runtime().set(option_name, value)
    return value


def process_bokeh_axis_title(ctx, param, value):
    """Processes default value for axes.

    If the value supplied from CLI is non-None, it is returned as it is. Otherwise, we try to
    create some optimal axis name. We do this according to the already processed parameters and
    we either use 'per_key' or 'of_key'.

    Arguments:
        ctx(click.Context): called context of the process
        param(click.Option): called option (either x or y axis)
        value(object): given value for the the option param

    Returns:
        object: either value (if it is non-None) or default legend for given axis
    """
    if value:
        return value
    elif param.human_readable_name.startswith('x'):
        if 'per_key' in ctx.params.keys():
            return ctx.params['per_key']
        elif 'through_key' in ctx.params.keys():
            return ctx.params['through_key']
        else:
            log.error("internal perun error")
    elif param.human_readable_name.startswith('y'):
        return ctx.params['of_key']
    else:
        log.error("internal perun error")


def process_resource_key_param(ctx, param, value):
    """Processes value for the key param (according to the profile)

    Checks the global context for stored profile, and obtains all of the keys, which serves
    as a validation list for the given values for the parameters. For X axis, snapshots are
    an additional valid parameter.

    Arguments:
        ctx(click.Context): called context of the process
        param(click.Option): called option that takes a valid key from profile as a parameter
        value(object): given value for the option param

    Returns:
        object: value or raises bad parameter

    Raises:
        click.BadParameter: if the value is invalid for the profile
    """
    if param.human_readable_name in ('per_key', 'through_key') and value == 'snapshots':
        return value
    # Validate the keys, if it is one of the set
    valid_keys = set(query.all_resource_fields_of(ctx.parent.params['profile']))
    if value not in valid_keys:
        error_msg_ending = ", snaphots" if param.human_readable_name == 'per_key' else ""
        raise click.BadParameter("invalid choice: {}. (choose from {})".format(
            value, ", ".join(str(vk) for vk in valid_keys) + error_msg_ending
        ))
    return value


def process_continuous_key(ctx, _, value):
    """Helper function for processing the continuous key for the param.

    Continuous keys are used in the continuous graphs (do'h!) on the x axis, i.e. they have to be
    numeric. We check all of the keys in the resources.

    Arguments:
        ctx(click.Context): called context of the process
        _(click.Option): called parameter
        value(object): given value for the option param

    Returns:
        object: value or raises bad parameter

    Raises:
        click.BadParameter: if the value is invalid for the profile
    """
    if value == 'snapshots':
        return value

    # Get all of the numerical keys
    valid_numeric_keys = set(query.all_numerical_resource_fields_of(ctx.parent.params['profile']))
    if value not in valid_numeric_keys:
        raise click.BadParameter("invalid choice: {}. (choose from {})".format(
            value, ", ".join(str(vnk) for vnk in valid_numeric_keys) + ", snapshots"
        ))
    return value
