import click

__author__ = 'Tomas Fiedor'


@click.group()
def cli():
    print("Hello World! From perun")


@cli.command()
def config():
    print("perun config run")


@cli.command()
def init():
    print("perun init run")


@cli.command()
def add():
    print("perun add run")


@cli.command()
def rm():
    print("perun rm run")


@cli.command()
def log():
    print("perun log run")


@cli.command()
def show():
    print("perun show run")


if __name__ == "__main__":
    cli()
