"""Set of helper functions for working with command line.

Contains functions for click api, for processing parameters from command line, validating keys,
and returning default values.
"""

import functools
import os
import re
import click

import perun
import perun.profile.factory as profiles
import perun.logic.commands as commands
import perun.logic.store as store
import perun.logic.config as config
import perun.logic.pcs as pcs
import perun.profile.query as query
import perun.utils.streams as streams
import perun.utils.log as log
import perun.vcs as vcs

from perun.utils.exceptions import VersionControlSystemException

__author__ = 'Tomas Fiedor'


def print_version(_, __, value):
    """Prints current version of Perun and ends"""
    if value:
        print("Perun {}".format(perun.__version__))
        exit(0)


def process_bokeh_axis_title(ctx, param, value):
    """Processes default value for axes.

    If the value supplied from CLI is non-None, it is returned as it is. Otherwise, we try to
    create some optimal axis name. We do this according to the already processed parameters and
    we either use 'per_key' or 'of_key'.

    :param click.Context ctx: called context of the process
    :param click.Option param: called option (either x or y axis)
    :param object value: given value for the the option param
    :returns object: either value (if it is non-None) or default legend for given axis
    """
    if value:
        return value
    elif param.human_readable_name.startswith('x'):
        if 'per_key' in ctx.params.keys():
            return ctx.params['per_key']
        elif 'through_key' in ctx.params.keys():
            return ctx.params['through_key']
        else:
            log.error("internal perun error: you need 'per_key' or 'through_key' in params")
    elif param.human_readable_name.startswith('y'):
        return ctx.params['of_key']


def process_resource_key_param(ctx, param, value):
    """Processes value for the key param (according to the profile)

    Checks the global context for stored profile, and obtains all of the keys, which serves
    as a validation list for the given values for the parameters. For X axis, snapshots are
    an additional valid parameter.

    :param click.Context ctx: called context of the process
    :param click.Option param: called option that takes a valid key from profile as a parameter
    :param object value: given value for the option param
    :returns object: value or raises bad parameter
    :raises click.BadParameter: if the value is invalid for the profile
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

    :param click.Context ctx: called context of the process
    :param click.Option _: called parameter
    :param object value: given value for the option param
    :returns object: value or raises bad parameter
    :raises click.BadParameter: if the value is invalid for the profile
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


def set_config_option_from_flag(dst_config_getter, config_option, postprocess_function=lambda x: x):
    """Helper function for setting the config option from the CLI option handler

    Returns the option handler, that sets, if value is equal to true, the config option to the
    given option value. This is e.g. used to use the CLI to set various configurations temporarily
    from the command line option.

    :param function dst_config_getter: destination config, where the option will be set
    :param str config_option: name of the option that will be set in the runtime config
    :param function postprocess_function: function which will postprocess the value
    :return: handler for the command line interface
    """
    def option_handler(_, __, value):
        """Wrapper handling function

        :param click.Context _: called context of the process
        :param click.Option __: called parameter
        :param object value: given value of the option param
        :return:
        """
        if value:
            dst_config_getter().set(config_option, postprocess_function(value))
        return value
    return option_handler


def yaml_param_callback(_, __, value):
    """Callback function for parsing the yaml files to dictionary object

    :param Context _: context of the called command
    :param click.Option __: parameter that is being parsed and read from commandline
    :param str value: value that is being read from the commandline
    :returns dict: parsed yaml file
    """
    unit_to_params = {}
    for (unit, yaml_file) in value:
        unit_to_params[unit] = streams.safely_load_yaml(yaml_file)
    return unit_to_params


def single_yaml_param_callback(_, __, value):
    """Callback function for parsing the yaml files to dictionary object, when called from 'collect'

    This does not require specification of the collector to which the params correspond and is
    meant as massaging of parameters for 'perun -p file collect ...' command.

    :param Context _: context of the called command
    :param click.Option __: parameter that is being parsed and read from commandline
    :param str value: value that is being read from the commandline
    :returns dict: parsed yaml file
    """
    unit_to_params = {}
    for yaml_file in value:
        # First check if this is file
        unit_to_params.update(streams.safely_load_yaml(yaml_file))
    return unit_to_params


def minor_version_list_callback(ctx, _, value):
    """Callback function for parsing the minor version list for running the automation

    :param Context ctx: context of the called command
    :param click.Option _: parameter that is being parsed and read from commandline
    :param str value: value that is being read from the commandline
    :returns list: list of MinorVersion objects
    """
    minors = []
    if value:
        for minor_version in value:
            massaged_version = vcs.massage_parameter(minor_version)
            # If we should crawl all of the parents, we collect them
            if ctx.params.get('crawl_parents', False):
                minors.extend(vcs.walk_minor_versions(massaged_version))
            # Otherwise we retrieve the minor version info for the param
            else:
                minors.append(vcs.get_minor_version_info(massaged_version))
    return minors


def unsupported_option_callback(_, param, value):
    """Processes the currently unsupported option or argument.

    :param click.Context _: called context of the parameter
    :param click.Option param: parameter we are processing
    :param Object value: value of the parameter we are trying to set
    """
    if value:
        err_msg = "option '{}'".format(param.human_readable_name)
        err_msg += "is unsupported/not implemented in this version of perun"
        err_msg += "\n\nPlease update your perun or wait patiently for the implementation"
        log.error(err_msg)


def config_key_validation_callback(_, param, value):
    """Validates whether the value of the key is in correct format---strings delimited by dot.

    :param click.Context _: called context of the command line
    :param click.Option param: called option (key in this case)
    :param object value: assigned value to the <key> argument
    :returns object: value for the <key> argument
    """
    if not config.is_valid_key(str(value)):
        err_msg = "<key> argument '{}' for {} config operation is in invalid format. ".format(
            value, str(param.param_type_name)
        )
        err_msg += "Valid key should be represented as sections delimited by dot (.), "
        err_msg += "e.g. general.paging is valid key."
        raise click.BadParameter(err_msg)
    return value


def vcs_parameter_callback(ctx, param, value):
    """Parses flags and parameters for version control system during the init

    Collects all flags (as flag: True) and parameters (as key value pairs) inside the
    ctx.params['vcs_params'] dictionary, which is then send to the initialization of vcs.

    :param Context ctx: context of the called command
    :param click.Option param: parameter that is being parsed
    :param str value: value that is being read from the commandline
    :returns tuple: tuple of flags or parameters
    """
    if 'vcs_params' not in ctx.params.keys():
        ctx.params['vcs_params'] = {}
    for vcs_param in value:
        if param.name.endswith("param"):
            ctx.params['vcs_params'][vcs_param[0]] = vcs_param[1]
        else:
            ctx.params['vcs_params'][vcs_param] = True
    return value


def lookup_nth_pending_filename(position):
    """Looks up the nth pending file from the sorted list of pending files

    :param int position: position of the pending we will lookup
    :returns str: pending profile at given position
    """
    pending = commands.get_untracked_profiles()
    profiles.sort_profiles(pending)
    if 0 <= position < len(pending):
        return pending[position].realpath
    else:
        raise click.BadParameter("invalid tag '{}' (choose from interval <{}, {}>)".format(
            "{}@p".format(position), '0@p', '{}@p'.format(len(pending)-1)
        ))


def lookup_added_profile_callback(_, __, value):
    """Callback function for looking up the profile which will be added/registered

    Profile can either be represented as a pending tag (e.g. 0@p), as a pending tag range
    (e.g. 0@p-5@p) or as a path to a file.

    :param Context _: context of the called command
    :param click.Option __: parameter that is being parsed and read from commandline
    :param str value: value that is being read from the commandline
    :returns str: filename of the profile
    """
    massaged_values = set()
    for single_value in value:
        pending_match = store.PENDING_TAG_REGEX.match(single_value)
        range_match = store.PENDING_TAG_RANGE_REGEX.match(single_value)
        if pending_match:
            massaged_values.add(lookup_nth_pending_filename(int(pending_match.group(1))))
        elif range_match:
            from_range, to_range = int(range_match.group(1)), int(range_match.group(2))
            for i in range(from_range, to_range+1):
                try:
                    massaged_values.add(lookup_nth_pending_filename(i))
                except click.BadParameter:
                    log.warn("skipping nonexisting tag {}@p".format(i))
        else:
            massaged_values.add(lookup_profile_in_filesystem(single_value))
    return massaged_values


def lookup_removed_profile_callback(ctx, _, value):
    """Callback function for looking up the profile which will be removed

    Profile can either be represented as an index tag (e.g. 0@i), as an index tag range (e.g.
    0@i-5@i) or as a path in the index

    :param Context ctx: context of the called command
    :param click.Option _: parameter that is being parsed and read from commandline
    :param str value: value that is being read from the commandline
    :returns str: filename of the profile to be removed
    """
    def add_to_removed(index):
        """Helper function for adding stuff to massaged values

        :param int index: index we are looking up and registering to massaged values
        """
        index_filename = commands.get_nth_profile_of(
            index, ctx.params['minor']
        )
        start = index_filename.rfind('objects') + len('objects')
        # Remove the .perun/objects/... prefix and merge the directory and file to sha
        massaged_values.add("".join(index_filename[start:].split('/')))

    massaged_values = set()
    for single_value in value:
        index_match = store.INDEX_TAG_REGEX.match(single_value)
        range_match = store.INDEX_TAG_RANGE_REGEX.match(single_value)
        if index_match:
            add_to_removed(int(index_match.group(1)))
        elif range_match:
            from_range, to_range = int(range_match.group(1)), int(range_match.group(2))
            for i in range(from_range, to_range+1):
                try:
                    add_to_removed(i)
                except click.BadParameter:
                    log.warn("skipping nonexisting tag {}@i".format(i))
        else:
            massaged_values.add(single_value)
    return massaged_values


def lookup_profile_in_filesystem(profile_name):
    """Helper function for looking up the profile in the filesystem

    First we check if the file is an absolute path, otherwise we lookup within the pending profile,
    i.e. in the .perun/jobs directory. If we still have not find the profile, we then iteratively
    explore the subfolders starting from current directory and look for a potential match.

    :param str profile_name: value that is being read from the commandline
    :returns str: full path to profile
    """
    # 1) if it exists return the value
    if os.path.exists(profile_name):
        return profile_name

    log.info("file '{}' does not exist. Checking pending jobs...".format(profile_name))
    # 2) if it does not exists check pending
    job_dir = pcs.get_job_directory()
    job_path = os.path.join(job_dir, profile_name)
    if os.path.exists(job_path):
        return job_path

    log.info("file '{}' not found in pending jobs...".format(profile_name))
    # 3) if still not found, check recursively all candidates for match and ask for confirmation
    searched_regex = re.compile(profile_name)
    for root, _, files in os.walk(os.getcwd()):
        for file in files:
            full_path = os.path.join(root, file)
            if file.endswith('.perf') and searched_regex.search(full_path):
                rel_path = os.path.relpath(full_path, os.getcwd())
                if click.confirm("did you perhaps mean '{}'?".format(rel_path)):
                    return full_path

    return profile_name


def lookup_minor_version_callback(_, __, value):
    """Callback for looking up the minor version, if it was not stated

    :param Context _: context of the called command
    :param click.Option __: parameter that is being parsed and read from commandline
    :param str value: value that is being read from the commandline
    :returns str: massaged minor version
    """
    if value:
        try:
            return vcs.massage_parameter(value)
        except VersionControlSystemException as exception:
            raise click.BadParameter(str(exception))


def lookup_any_profile_callback(ctx, _, value):
    """Callback for looking up any profile, i.e. anywhere (in index, in pending, etc.)

    :param click.core.Context ctx: context
    :param click.core.Argument _: param
    :param str value: value of the profile parameter
    """
    # 0) First check if the value is tag or not
    index_tag_match = store.INDEX_TAG_REGEX.match(value)
    if index_tag_match:
        index_profile = commands.get_nth_profile_of(
            int(index_tag_match.group(1)), ctx.params['minor']
        )
        return store.load_profile_from_file(index_profile, is_raw_profile=False)

    pending_tag_match = store.PENDING_TAG_REGEX.match(value)
    if pending_tag_match:
        pending_profile = lookup_nth_pending_filename(int(pending_tag_match.group(1)))
        return store.load_profile_from_file(pending_profile, is_raw_profile=True)

    # 1) Check the index, if this is registered
    profile_from_index = commands.load_profile_from_args(value, ctx.params['minor'])
    if profile_from_index:
        return profile_from_index

    log.info("file '{}' not found in index. Checking filesystem...".format(value))
    # 2) Else lookup filenames and load the profile
    abs_path = lookup_profile_in_filesystem(value)
    if not os.path.exists(abs_path):
        log.error("could not lookup the profile '{}'".format(abs_path))

    return store.load_profile_from_file(abs_path, is_raw_profile=True)


def resources_key_options(func):
    """
    This method creates Click decorator for common options for  all non-parametric
    postprocessor: `regressogram`, `moving average` and `kernel-regression`.


    :param function func: the function in which the decorator of common options is currently applied
    :return: returns sequence of the single options for the current function (f) as decorators
    """
    options = [
        click.option('--per-key', '-per', 'per_key', default='structure-unit-size',
                     nargs=1, metavar='<per_resource_key>', callback=process_resource_key_param,
                     help='Sets the key that will be used as a source variable (x-coordinates).'),
        click.option('--of-key', '-of', 'of_key', nargs=1, metavar='<of_resource_key>',
                     default='amount', callback=process_resource_key_param,
                     help='Sets key for which we are finding the model (y-coordinates).')
    ]
    return functools.reduce(lambda x, option: option(x), options, func)
