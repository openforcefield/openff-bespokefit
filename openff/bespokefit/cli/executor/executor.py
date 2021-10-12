import click

from openff.bespokefit.cli.executor.launch import launch_cli
from openff.bespokefit.cli.executor.list import list_cli
from openff.bespokefit.cli.executor.run import run_cli
from openff.bespokefit.cli.executor.submit import submit_cli
from openff.bespokefit.cli.executor.watch import watch_cli


@click.group("executor")
def executor_cli():
    """Commands for interacting with a bespoke executor."""


executor_cli.add_command(launch_cli)
executor_cli.add_command(submit_cli)
executor_cli.add_command(run_cli)
executor_cli.add_command(watch_cli)
executor_cli.add_command(list_cli)
