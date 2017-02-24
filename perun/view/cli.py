"""Command Line Interface for the Perun performance control.

Simple Command Line Interface for the Perun functionality using the Click library,
calls underlying commands from the commands module.
"""

import logging
import os

import click

import perun.utils.log as perun_log
import perun.core.logic.commands as commands

__author__ = 'Tomas Fiedor'


@click.group()
@click.option('--verbose', '-v', count=True, default=0,
              help='sets verbosity of the perun log')
def cli(verbose):
    """
    Arguments:
        verbose(int): how verbose the run of the perun is
    """
    perun_log.msg_to_stdout("Starting perun...", 0, logging.INFO)

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


@cli.command()
@click.argument('dst', required=False, default=os.getcwd())
@click.option('--init-vcs-type',
              help="additionally inits the vcs of the given type")
@click.option('--init-vcs-url',
              help="additionally inits the vcs at the given url")
@click.option('--init-vcs-params',
              help="additional params feeded to the init-vcs")
def init(dst, **kwargs):
    """
    Arguments:
        dst(str): destination, where the perun will be initialized
        kwargs(dict): dictionary of additional params to init
    """
    perun_log.msg_to_stdout("Running 'perun init'", 2, logging.INFO)
    commands.init(dst, **kwargs)


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
@click.option('--short-minors', '-s', is_flag=True, default=False,
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
@click.option('--coloured', '-c', is_flag=True,
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


@click.command()
def run(**kwargs):
    """
    Arguments:
        kwargs(dict): dictionary of keyword arguments
    """
    perun_log.msg_to_stdout("Running 'perun run'", 2, logging.INFO)
    commands.run(**kwargs)


if __name__ == "__main__":
    cli()
