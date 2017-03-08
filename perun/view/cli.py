"""Command Line Interface for the Perun performance control.

Simple Command Line Interface for the Perun functionality using the Click library,
calls underlying commands from the commands module.
"""

import logging
import os

import click

import perun.utils.log as perun_log
import perun.core.logic.config as perun_config
import perun.core.logic.commands as commands

from perun.utils.helpers import CONFIG_UNIT_ATTRIBUTES
from perun.core.logic.pcs import PCS

__author__ = 'Tomas Fiedor'


@click.group()
@click.option('--verbose', '-v', count=True, default=0,
              help='sets verbosity of the perun log')
def cli(verbose):
    """
    Arguments:
        verbose(int): how verbose the run of the perun is
    """
    # set the verbosity level of the log
    if perun_log.VERBOSITY < verbose:
        perun_log.VERBOSITY = verbose


@cli.command()
@click.argument('key', required=True)
@click.argument('value', required=False)
@click.option('--get', '-g', is_flag=True,
              help="get the value of the key")
@click.option('--set', '-s', is_flag=True,
              help="set the value of the key")
def config(key, value, **kwargs):
    """
    Arguments:
        key(str): key in config file, set of sections divided by dot (.)
        value(various): value that can optionally be set in config
        kwargs(dict): dictionary of keyword arguments
    """
    perun_log.msg_to_stdout("Running 'perun config'", 2, logging.INFO)
    commands.config(key, value, **kwargs)


def register_unit(pcs, unit_name):
    """
    Arguments:
        pcs(PCS): perun repository wrapper
        unit_name(str): name of the unit
    """
    unit_params = CONFIG_UNIT_ATTRIBUTES[unit_name]

    perun_log.quiet_info("\nRegistering new {} unit".format(unit_name))
    if not unit_params:
        added_unit_name = click.prompt('name')
        # Add to config
        perun_config.append_key_at_config(pcs.local_config(), unit_name, added_unit_name)
    else:
        # Obtain each parameter for the given unit_name
        added_unit = {}
        for param in unit_params:
            if param.endswith('args'):
                param_value = click.prompt(param + "( -- separated list)")
            else:
                param_value = click.prompt(param)
            added_unit[param] = param_value.split(' -- ')
        # Append to config
        perun_config.append_key_at_config(pcs.local_config(), unit_name, added_unit)
    click.pause()


def unregister_unit(pcs):
    """
    Arguments:
        pcs(PCS): perun repository wrapper
    """
    pass


def get_unit_list_from_config(perun_config, unit_type):
    """
    Arguments:
        perun_config(dict): dictionary config
        unit_type(str): type of the attribute we are getting

    Returns:
        list: list of units from config
    """
    unit_plural = unit_type + 's'
    is_iterable = unit_plural in ['collectors', 'postprocessors']

    if unit_plural in perun_config.keys():
        return [(unit_type, u.name if is_iterable else u) for u in perun_config[unit_plural]]
    else:
        return []


def list_units(pcs, do_confirm=True):
    """List the registered units inside the configuration of the perun in the following format.

    Unit_no. Unit [Unit_type]

    Arguments:
        pcs(PCS): perun repository wrapper
        do_confirm(bool): true if we should Press any key to continue
    """
    local_config = pcs.local_config().data
    units = []
    units.extend(get_unit_list_from_config(local_config, 'bin'))
    units.extend(get_unit_list_from_config(local_config, 'workload'))
    units.extend(get_unit_list_from_config(local_config, 'collector'))
    units.extend(get_unit_list_from_config(local_config, 'postprocessor'))
    unit_list = list(enumerate(units))
    perun_log.quiet_info("")
    if not unit_list:
        perun_log.quiet_info("no units registered yet")
    else:
        for unit_no, (unit_type, unit_name) in unit_list:
            perun_log.quiet_info("{}. {} [{}]".format(unit_no, unit_name, unit_type))

    if do_confirm:
        click.pause()

    return unit_list


__config_functions__ = {
    'b': lambda pcs: register_unit(pcs, "bins"),
    'w': lambda pcs: register_unit(pcs, "workloads"),
    'c': lambda pcs: register_unit(pcs, "collectors"),
    'p': lambda pcs: register_unit(pcs, "postprocessors"),
    'l': list_units,
    'r': unregister_unit,
    'q': lambda pcs: exit(0)
}


def configure_local_perun(perun_path):
    """Configures the local perun repository with the interactive help of the user

    Arguments:
        perun_path(str): destination path of the perun repository
    """
    invalid_option_happened = False
    while True:
        click.clear()
        if invalid_option_happened:
            perun_log.warn("invalid option '{}'".format(option))
            invalid_option_happened = False
        perun_log.quiet_info("Welcome to the interactive configuration of Perun!")
        click.echo("[b] Register new binary/application run command")
        click.echo("[w] Register application workload")
        click.echo("[c] Register collector")
        click.echo("[p] Register postprocessor")
        click.echo("[l] List registered units")
        click.echo("[r] Remove registered unit")
        click.echo("[q] Quit")

        click.echo("\nAction:", nl=False)
        option = click.getchar()
        if option not in __config_functions__.keys():
            invalid_option_happened = True
            continue
        __config_functions__.get(option)(PCS(perun_path))


@cli.command()
@click.argument('dst', required=False, default=os.getcwd())
@click.option('--vcs-type',
              help="additionally inits the vcs of the given type")
@click.option('--vcs-path',
              help="additionally inits the vcs at the given url")
@click.option('--vcs-params',
              help="additional params feeded to the init-vcs")
@click.option('--configure', '-c', is_flag=True, default=False,
              help='Runs the interactive initialization of the local configuration for the perun')
def init(dst, configure, **kwargs):
    """
    Arguments:
        dst(str): destination, where the perun will be initialized
        configure(bool): true if the perun repository local config should be initialized
        kwargs(dict): dictionary of additional params to init
    """
    perun_log.msg_to_stdout("Running 'perun init'", 2, logging.INFO)
    commands.init(dst, **kwargs)

    if configure:
        # Run the interactive configuration of the local perun repository (populating .yml)
        configure_local_perun(dst)
    else:
        perun_log.quiet_info("\nIn order to automatically run the jobs configure the matrix at:\n"
                             "\n"
                             + (" "*4) + ".perun/local.yml\n")


@cli.command()
@click.argument('profile', required=True)
@click.argument('minor', required=False, default=None)
def add(profile, minor):
    """
    Arguments:
        profile(str): path to the profile file or sha1
        minor(str): sha1 representation of the minor version for which the profile is assigned
    """
    perun_log.msg_to_stdout("Running 'perun add'", 2, logging.INFO)
    commands.add(profile, minor)


@cli.command()
@click.argument('profile', required=True)
@click.argument('minor', required=False, default=None)
@click.option('--remove-all', '-A', is_flag=True, default=False,
              help="remove all profiles of the given name/sha-1")
def rm(profile, minor, **kwargs):
    """
    Arguments:
        profile(str): path to the profile file or sha1
        minor(str): sha1 representation of the minor version for which the profile is removed
        kwargs(dict): dictionary of the keyword arguments
    """
    perun_log.msg_to_stdout("Running 'perun rm'", 2, logging.INFO)
    commands.remove(profile, minor, **kwargs)


@cli.command()
@click.argument('head', required=False, default=None)
@click.option('--count-only', is_flag=True, default=False,
              help="force printing of the profile count only associated to minor versions")
@click.option('--show-aggregate', is_flag=True, default=False,
              help="show aggregated profiles (one-liners) per each minor version")
@click.option('--last', default=-1,
              help="show only last N minor versions")
@click.option('--no-merged', is_flag=True, default=False,
              help="if set the merges of paths will not be displayed")
@click.option('--short', '-s', is_flag=True, default=False,
              help="displays the minor version informations in short format")
def log(head, **kwargs):
    """
    Arguments:
        head(str): head minor version
        kwargs(dict): various keyword arguments that changes how the log is displayed
    """
    perun_log.msg_to_stdout("Running 'perun log'", 2, logging.INFO)
    commands.log(head, **kwargs)


@cli.command()
@click.option('--short', '-s', required=False, default=False, is_flag=True,
              help="print the current status in short format instead of long format")
def status(**kwargs):
    """
    Arguments:
        kwargs(dict): various keyword arguments that changes how the status is displayed
    """
    perun_log.msg_to_stdout("Running 'perun status'", 2, logging.INFO)
    commands.status(**kwargs)


@cli.command()
@click.argument('profile', required=True)
@click.argument('minor', required=False)
@click.option('--format', '-f', type=click.Choice(['raw']), default='raw',
              help="how the profile should be shown")
@click.option('--coloured', '-c', is_flag=True, default=False,
              help="colour the outputed profile")
@click.option('--one-line', '-o', is_flag=True,
              help="print the agggregated one-line data for the given profile")
def show(profile, minor, **kwargs):
    """
    TODO: Check that if profile is not SHA-1, then minor must be set
    Arguments:
        profile(str): either path to profile or sha1 object representation
        minor(str): sha1 representation of the minor version
        kwargs(dict): additional arguments to perun show
    """
    perun_log.msg_to_stdout("Running 'perun show'", 2, logging.INFO)
    commands.show(profile, minor, **kwargs)


@cli.group()
def run():
    """Group for running the jobs either from cmd or from stored config"""
    perun_log.msg_to_stdout("Running 'perun run'", 2, logging.INFO)


@run.command()
def matrix(**kwargs):
    """
    Arguments:
        kwargs(dict): dictionary of keyword arguments
    """
    commands.run_matrix_job(**kwargs)


@run.command()
@click.option('--bin', '-b', nargs=1, required=True, multiple=True,
              help='binary that the job will be run for')
@click.option('--args', '-a', nargs=1, required=False, multiple=True,
              help='additional arguments for the binary')
@click.option('--workload', '-w', nargs=1, required=True, multiple=True,
              help='workload for the job')
@click.option('--collector', '-c', nargs=1, required=True, multiple=True,
              help='collector used to collect the data')
@click.option('--postprocessor', '-p', nargs=1, required=False, multiple=True,
              help='additional postprocessing phases')
def job(**kwargs):
    """
    TODO: Add choice to collector/postprocessors from the registered shits
    Arguments:
        kwargs(dict): dictionary of keyword arguments
    """
    commands.run_single_job(**kwargs)


if __name__ == "__main__":
    cli()
