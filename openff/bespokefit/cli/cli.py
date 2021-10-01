import click

from openff.bespokefit.cli.executor import executor_cli
from openff.bespokefit.cli.prepare import prepare_cli


@click.group()
def cli():
    """The root group for all CLI commands."""


cli.add_command(executor_cli)
cli.add_command(prepare_cli)
