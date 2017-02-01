import click
import logging
import perun.utils.log

__author__ = 'Tomas Fiedor'


@click.group()
@click.option('--verbose', '-v', count=True,
              help='sets verbosity of the perun log')
def cli(verbose):
    perun.utils.log.msg_to_stdout("Starting perun...", 0, logging.INFO)

    # set the verbosity level of the log
    perun.utils.log.verbosity = verbose


@cli.command()
def config():
    perun.utils.log.msg_to_stdout("Running 'perun config'", 2, logging.INFO)


@cli.command()
def init():
    perun.utils.log.msg_to_stdout("Running 'perun init'", 2, logging.INFO)


@cli.command()
def add():
    perun.utils.log.msg_to_stdout("Running 'perun add'", 2, logging.INFO)


@cli.command()
def rm():
    perun.utils.log.msg_to_stdout("Running 'perun rm'", 2, logging.INFO)


@cli.command()
def log():
    perun.utils.log.msg_to_stdout("Running 'perun log'", 2, logging.INFO)


@cli.command()
def show():
    perun.utils.log.msg_to_stdout("Running 'perun show'", 2, logging.INFO)


if __name__ == "__main__":
    cli()
