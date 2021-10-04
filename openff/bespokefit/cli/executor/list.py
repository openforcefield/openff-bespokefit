import click
import requests
import rich
from rich import pretty
from rich.padding import Padding

from openff.bespokefit.cli.utilities import print_header


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

    href = (
        f"http://127.0.0.1:"
        f"{settings.BEFLOW_GATEWAY_PORT}"
        f"{settings.BEFLOW_API_V1_STR}/"
        f"{settings.BEFLOW_COORDINATOR_PREFIX}"
    )

    try:

        request = requests.get(href)
        request.raise_for_status()

    except requests.ConnectionError:
        console.print(
            "A connection could not be made to the bespoke executor. Please make sure "
            "there is a bespoke executor running."
        )
        return

    response = CoordinatorGETPageResponse.parse_raw(request.content)
    response_ids = [item.id for item in response.contents]

    if len(response_ids) == 0:
        console.print("No optimizations were found.")
        return

    console.print(Padding("The following optimizations were found:", (0, 0, 1, 0)))
    console.print("\n".join(response_ids))
