import click

__author__ = 'Tomas Fiedor'


@click.group()
def cli():
    print("Hello World! From perun")

if __name__ == "__main__":
    cli()
