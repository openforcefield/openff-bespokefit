from typing import Tuple, get_args

import click
import click.exceptions
import requests
import rich
from rich import pretty
from rich.table import Table

from openff.bespokefit.cli.utilities import print_header
from openff.bespokefit.schema import Status

_STATUS_STRINGS = {
    "waiting": "[grey]waiting[/grey]",
    "running": "[yellow]running[/yellow]",
    "success": "[green]success[/green]",
    "errored": "[red]errored[/red]",
}


def _get_columns(console: "rich.Console", optimization_id: str) -> Tuple[str, "Status"]:
    from openff.toolkit.topology import Molecule

    from openff.bespokefit.executor import BespokeExecutor
    from openff.bespokefit.executor.utilities import handle_common_errors

    with handle_common_errors(console) as error_state:
        output = BespokeExecutor.retrieve(optimization_id)
    if error_state["has_errored"]:
        raise click.exceptions.Exit(code=2)

    smiles = Molecule.from_smiles(output.smiles).to_smiles(
        isomeric=True, explicit_hydrogens=False, mapped=False
    )

    return smiles, output.status


@click.option(
    "--status",
    "status_filter",
    type=click.Choice(get_args(Status)),
    help="The (optional) status to filter by",
    required=False,
)
@click.command("list")
def list_cli(status_filter: Status):
    """List the ids of any bespoke optimizations."""

    pretty.install()

    console = rich.get_console()
    print_header(console)

    from openff.bespokefit.executor.services import current_settings
    from openff.bespokefit.executor.services.coordinator.models import (
        CoordinatorGETPageResponse,
    )
    from openff.bespokefit.executor.utilities import handle_common_errors

    settings = current_settings()

    # In the coordinator we keep both successful and errored tasks in the same 'complete'
    # queue to avoid having to maintain and query to separate lists in redis, so here we
    # need to condense these two states into one and then apply a second filter when
    # iterating over the returned ids.
    status_url = (
        None
        if status_filter is None
        else status_filter.replace("success", "complete").replace("errored", "complete")
    )
    status_url = "" if status_url is None else f"?status={status_url}"

    base_href = (
        f"http://127.0.0.1:"
        f"{settings.BEFLOW_GATEWAY_PORT}"
        f"{settings.BEFLOW_API_V1_STR}/"
        f"{settings.BEFLOW_COORDINATOR_PREFIX}"
        f"{status_url}"
    )

    with handle_common_errors(console) as error_state:
        request = requests.get(base_href)
        request.raise_for_status()

    if error_state["has_errored"]:
        raise click.exceptions.Exit(code=2)

    response = CoordinatorGETPageResponse.parse_raw(request.content)
    records = []

    for item in response.contents:
        smiles, status = _get_columns(console, item.id)

        if status_filter is not None and status != status_filter:
            continue

        records.append((item.id, smiles, status))

    if len(records) == 0:
        status_message = (
            "."
            if status_filter is None
            else f" with status {_STATUS_STRINGS[status_filter]}"
        )
        console.print(f"No optimizations were found{status_message}")

        return

    table = Table()

    table.add_column("ID", justify="center", no_wrap=True)
    table.add_column("SMILES", overflow="fold")
    table.add_column("STATUS", no_wrap=True)

    for record_id, smiles, status in records:
        smiles, status = _get_columns(console, record_id)

        if status_filter is not None and status != status_filter:
            continue

        status_string = _STATUS_STRINGS[status]

        table.add_row(record_id, smiles, status_string)

    console.print("The following optimizations were found:")
    console.print(table)
