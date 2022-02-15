from typing import Optional

import click
import click.exceptions
import requests
import rich
from rich import pretty
from rich.table import Table

from openff.bespokefit.cli.utilities import print_header


def _get_smiles(console: "rich.Console", optimization_id: str) -> Optional[str]:

    from openff.toolkit.topology import Molecule

    from openff.bespokefit.executor.services import settings
    from openff.bespokefit.executor.services.coordinator.models import (
        CoordinatorGETResponse,
    )
    from openff.bespokefit.executor.utilities import handle_common_errors

    href = (
        f"http://127.0.0.1:"
        f"{settings.BEFLOW_GATEWAY_PORT}"
        f"{settings.BEFLOW_API_V1_STR}/"
        f"{settings.BEFLOW_COORDINATOR_PREFIX}/{optimization_id}"
    )

    with handle_common_errors(console) as error_state:
        request = requests.get(href)
        request.raise_for_status()
    if error_state["has_errored"]:
        return None

    cmiles = CoordinatorGETResponse.parse_raw(request.content).smiles
    smiles = Molecule.from_smiles(cmiles).to_smiles(
        isomeric=True, explicit_hydrogens=False, mapped=False
    )

    return smiles


@click.command("list")
def list_cli():
    """List the ids of any bespoke optimizations."""

    pretty.install()

    console = rich.get_console()
    print_header(console)

    from openff.bespokefit.executor.services import settings
    from openff.bespokefit.executor.services.coordinator.models import (
        CoordinatorGETPageResponse,
    )
    from openff.bespokefit.executor.utilities import handle_common_errors

    base_href = (
        f"http://127.0.0.1:"
        f"{settings.BEFLOW_GATEWAY_PORT}"
        f"{settings.BEFLOW_API_V1_STR}/"
        f"{settings.BEFLOW_COORDINATOR_PREFIX}"
    )

    with handle_common_errors(console) as error_state:

        request = requests.get(base_href)
        request.raise_for_status()

    if error_state["has_errored"]:
        raise click.exceptions.Exit(code=2)

    response = CoordinatorGETPageResponse.parse_raw(request.content)

    if len(response.contents) == 0:
        console.print("No optimizations were found.")
        return

    table = Table()

    table.add_column("ID", justify="center", no_wrap=True)
    table.add_column("SMILES", overflow="fold")

    for item in response.contents:
        table.add_row(item.id, _get_smiles(console, item.id))

    console.print("The following optimizations were found:")
    console.print(table)
