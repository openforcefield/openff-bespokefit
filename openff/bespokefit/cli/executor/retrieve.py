import click
import rich
from rich import pretty
from rich.padding import Padding

from openff.bespokefit.cli.utilities import print_header
from openff.bespokefit.executor.utilities import handle_common_errors


@click.command("retrieve")
@click.option(
    "--id",
    "optimization_id",
    type=click.STRING,
    help="The id of the optimization to retrieve",
    required=True,
)
@click.option(
    "--output",
    "output_file_path",
    type=click.Path(exists=False, file_okay=True, dir_okay=False),
    help="The JSON file to save the results to",
    default="output.json",
    show_default=True,
)
def retrieve_cli(optimization_id, output_file_path):
    """Watch the status of a bespoke optimization."""

    pretty.install()

    console = rich.get_console()
    print_header(console)

    from openff.bespokefit.executor import BespokeExecutor

    with handle_common_errors(console) as error_state:
        results = BespokeExecutor.retrieve(optimization_id)
    if error_state["has_errored"]:
        return

    message = "the bespoke fit is"

    if results.status == "waiting":
        console.print(f"[[grey]⧖[/grey]] {message} queued")
    elif results.status == "running":
        console.print(f"[[yellow]↻[/yellow]] {message} running")
    elif results.status == "errored":
        console.print(f"[[red]x[/red]] {message} errored")
    elif results.status == "success":
        console.print(f"[[green]✓[/green]] {message} finished")
    else:
        raise NotImplementedError()

    console.print(
        Padding(
            f"outputs have been saved to "
            f"[repr.filename]{output_file_path}[/repr.filename]",
            (1, 0, 1, 0),
        )
    )

    with open(output_file_path, "w") as file:
        file.write(results.json())
