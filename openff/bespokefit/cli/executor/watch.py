import click
import rich
from rich import pretty

from openff.bespokefit.cli.utilities import print_header


@click.command("watch")
@click.option(
    "--id",
    "optimization_id",
    type=click.STRING,
    help="The id of the optimization to watch",
    required=True,
)
def watch_cli(optimization_id):
    """Watch the status of a bespoke optimization."""

    pretty.install()

    console = rich.get_console()
    print_header(console)

    from openff.bespokefit.executor import wait_until_complete

    wait_until_complete(optimization_id)
