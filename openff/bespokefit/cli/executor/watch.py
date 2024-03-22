"""Host of `watch` command in CLI."""

import click
import click.exceptions
import rich
from rich import pretty

from openff.bespokefit.cli.utilities import print_header
from openff.bespokefit.executor.utilities import handle_common_errors


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

    with handle_common_errors(console) as error_state:
        wait_until_complete(optimization_id)
    if error_state["has_errored"]:
        raise click.exceptions.Exit(code=2)
