import click
import logging
import os
import perun.utils.log
import perun.core.logic.commands as commands

__author__ = 'Tomas Fiedor'


@click.group()
@click.option('--verbose', '-v', count=True,
              help='sets verbosity of the perun log')
def cli(verbose):
    perun.utils.log.msg_to_stdout("Starting perun...", 0, logging.INFO)

    # set the verbosity level of the log
    if perun.utils.log.verbosity < verbose:
        perun.utils.log.verbosity = verbose


@cli.command()
@click.argument('key', required=True)
@click.argument('value', required=False)
@click.option('--get', '-g', is_flag=True,
              help="get the value of the key")
@click.option('--set', '-s', is_flag=True,
              help="set the value of the key")
def config(*args, **kwargs):
    perun.utils.log.msg_to_stdout("Running 'perun config'", 2, logging.INFO)
    commands.config(*args, **kwargs)


@cli.command()
@click.argument('dst', required=False, default=os.getcwd())
@click.option('--init-vcs-type',
              help="additionally inits the vcs of the given type")
@click.option('--init-vcs-url',
              help="additionally inits the vcs at the given url")
@click.option('--init-vcs-params',
              help="additional params feeded to the init-vcs")
def init(dst, **kwargs):
    perun.utils.log.msg_to_stdout("Running 'perun init'", 2, logging.INFO)
    commands.init(dst, **kwargs)


@cli.command()
@click.argument('profile', required=True)
@click.argument('minor', required=False, default=None)
def add(profile, minor, **kwargs):
    perun.utils.log.msg_to_stdout("Running 'perun add'", 2, logging.INFO)
    commands.add(profile, minor)


@cli.command()
@click.argument('minor', required=False, default=None)
@click.argument('profile', required=True, nargs=-1)
def rm(minor, profile, **kwargs):
    perun.utils.log.msg_to_stdout("Running 'perun rm'", 2, logging.INFO)
    commands.rm(profile, minor)


@cli.command()
@click.option('--count-only', is_flag=True,
              help="force printing of the profile count only associated to minor versions")
@click.option('--show-aggregate', is_flag=True,
              help="show aggregated profiles (one-liners) per each minor version")
@click.option('--last', default=-1,
              help="show only last N minor versions")
def log(**kwargs):
    perun.utils.log.msg_to_stdout("Running 'perun log'", 2, logging.INFO)
    commands.log(None)


@cli.command()
@click.option('--coloured', '-c', is_flag=True,
              help="colour the outputed profile")
@click.option('--one-line', '-o', is_flag=True,
              help="print the agggregated one-line data for the given profile")
def show(**kwargs):
    perun.utils.log.msg_to_stdout("Running 'perun show'", 2, logging.INFO)
    commands.show(None, None, None)


@click.command()
def run(**kwargs):
    perun.utils.log.msg_to_stdout("Running 'perun run'", 2, logging.INFO)
    commands.run(None)


if __name__ == "__main__":
    cli()
