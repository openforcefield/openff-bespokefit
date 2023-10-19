"""BespokeFit CLI."""
import click

from openff.bespokefit.cli.cache import cache_cli
from openff.bespokefit.cli.combine import combine_cli
from openff.bespokefit.cli.executor import executor_cli
from openff.bespokefit.cli.prepare import prepare_cli


@click.group()
def cli():
    """Root group for all CLI commands."""


cli.add_command(executor_cli)
cli.add_command(prepare_cli)
cli.add_command(cache_cli)
cli.add_command(combine_cli)
