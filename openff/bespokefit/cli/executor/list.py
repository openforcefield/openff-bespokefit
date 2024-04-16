from typing import get_args

import click

from openff.bespokefit.cli.utilities import print_header
from openff.bespokefit.schema import Status

_STATUS_STRINGS = {
    "waiting": "[grey]waiting[/grey]",
    "running": "[yellow]running[/yellow]",
    "success": "[green]success[/green]",
    "errored": "[red]errored[/red]",
}


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
    import click.exceptions
    import rich
    from openff.toolkit import Molecule
    from rich import pretty
    from rich.table import Table

    from openff.bespokefit.executor.client import BespokeFitClient
    from openff.bespokefit.executor.services import current_settings
    from openff.bespokefit.executor.utilities import handle_common_errors

    pretty.install()

    console = rich.get_console()
    print_header(console)

    settings = current_settings()

    client = BespokeFitClient(settings=settings)

    with handle_common_errors(console) as error_state:
        response = client.list_optimizations(status=status_filter)

    if error_state["has_errored"]:
        raise click.exceptions.Exit(code=2)

    records = []

    for item in response.contents:
        with handle_common_errors(console) as error_state:
            output = client.get_optimization(optimization_id=item.id)

        if error_state["has_errored"]:
            raise click.exceptions.Exit(code=2)

        smiles = Molecule.from_smiles(output.smiles).to_smiles(
            isomeric=True, explicit_hydrogens=False, mapped=False
        )
        status = output.status

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

        if status_filter is not None and status != status_filter:
            continue

        status_string = _STATUS_STRINGS[status]

        table.add_row(record_id, smiles, status_string)

    console.print(
        f"The following optimizations were found on Bespoke-Executor: {client.address}"
    )
    console.print(table)
