import os.path
from typing import TYPE_CHECKING, Optional

import click
import rich
from click_option_group import optgroup
from openff.utilities import get_data_file_path
from pydantic import ValidationError
from rich import pretty
from rich.padding import Padding

from openff.bespokefit.cli.utilities import create_command, print_header
from openff.bespokefit.executor.utilities import handle_common_errors

if TYPE_CHECKING:
    from openff.toolkit.topology import Molecule

    from openff.bespokefit.schema.fitting import BespokeOptimizationSchema


# The run command inherits these options so be sure to take that into account when
# making changes here.
def submit_options():
    return [
        click.option(
            "--file",
            "input_file_path",
            type=click.Path(exists=True, file_okay=True, dir_okay=False),
            help="The file containing the molecule of interest",
            required=False,
        ),
        click.option(
            "--smiles",
            "molecule_smiles",
            type=click.STRING,
            help="The SMILES string representation of the input molecule.",
            required=False,
        ),
        click.option(
            "--force-field",
            "force_field_path",
            type=click.Path(exists=False, file_okay=True, dir_okay=False),
            help="The initial force field to build upon. This will overwrite the value "
            "in the workflow spec if provided.",
            default=None,
            show_default=True,
            required=False,
        ),
        optgroup.group("Optimization configuration"),
        optgroup.option(
            "--spec",
            "spec_name",
            type=click.Choice(choices=["default", "debug"], case_sensitive=False),
            help="The name of the built-in configuration to use",
            required=False,
        ),
        optgroup.option(
            "--spec-file",
            "spec_file_name",
            type=click.Path(exists=False, file_okay=True, dir_okay=False),
            help="The path to a serialized bespoke workflow factory",
            required=False,
        ),
    ]


def _to_input_schema(
    console: "rich.Console",
    molecule: "Molecule",
    force_field_path: Optional[str],
    spec_name: Optional[str],
    spec_file_name: Optional[str],
) -> Optional["BespokeOptimizationSchema"]:

    from openff.bespokefit.workflows.bespoke import BespokeWorkflowFactory

    if (spec_name is not None and spec_file_name is not None) or (
        spec_name is None and spec_file_name is None
    ):

        console.print(
            "[[red]ERROR[/red] The `spec` and `spec-file` arguments are mutually "
            "exclusive"
        )
        return None

    invalid_spec_name = spec_name if spec_name is not None else spec_file_name

    try:

        if spec_name is not None:

            spec_file_name = get_data_file_path(
                os.path.join("schemas", f"{spec_name.lower()}.json"),
                "openff.bespokefit",
            )

        workflow_factory = BespokeWorkflowFactory.from_file(spec_file_name)

        if force_field_path is not None:
            workflow_factory.initial_force_field = force_field_path

    except (FileNotFoundError, RuntimeError) as e:

        # Need for QCSubmit #176
        if isinstance(e, RuntimeError) and "could not be found" not in str(e):
            raise e

        console.print(
            Padding(
                f"[[red]ERROR[/red]] The specified schema could not be found: "
                f"[repr.filename]{invalid_spec_name}[/repr.filename]",
                (1, 0, 0, 0),
            )
        )

        return

    except ValidationError as e:

        console.print(
            Padding(
                f"[[red]ERROR[/red]] The factory schema could not be parsed. Make sure "
                f"[repr.filename]{invalid_spec_name}[/repr.filename] is a valid "
                f"`BespokeWorkflowFactory` schema.",
                (1, 0, 0, 0),
            )
        )
        console.print(Padding(str(e), (1, 1, 1, 1)))

        return

    return workflow_factory.optimization_schema_from_molecule(molecule)


def _submit(
    console: "rich.Console",
    input_file_path: Optional[str],
    molecule_smiles: Optional[str],
    force_field_path: Optional[str],
    spec_name: Optional[str],
    spec_file_name: Optional[str],
) -> str:

    from openff.toolkit.topology import Molecule

    from openff.bespokefit.executor import BespokeExecutor

    console.print(Padding("1. preparing the bespoke workflow", (0, 0, 1, 0)))

    if input_file_path is not None:
        with console.status("loading the molecules"):
            molecule = Molecule.from_file(input_file_path)

    else:
        with console.status("creating molecule from smiles"):
            molecule = Molecule.from_smiles(molecule_smiles)

    if not isinstance(molecule, Molecule) or "." in molecule.to_smiles():
        console.print(
            "[[red]ERROR[/red]] only one molecule can currently be submitted at "
            "a time"
        )
        return

    console.print("[[green]✓[/green]] [blue]1[/blue] molecule was found")

    with console.status("building fitting schemas"):

        input_schema = _to_input_schema(
            console, molecule, force_field_path, spec_name, spec_file_name
        )

        if input_schema is None:
            return

    console.print("[[green]✓[/green]] fitting schema generated")

    console.print(Padding("2. submitting the workflow", (1, 0, 1, 0)))

    response_id = BespokeExecutor.submit(input_schema)
    console.print(f"[[green]✓[/green]] workflow submitted: id={response_id}")

    return response_id


def _submit_cli(
    input_file_path: Optional[str],
    molecule_smiles: Optional[str],
    force_field_path: Optional[str],
    spec_name: Optional[str],
    spec_file_name: Optional[str],
):
    """Submit a new bespoke optimization to a running executor."""

    pretty.install()

    console = rich.get_console()
    print_header(console)

    if (input_file_path is not None and molecule_smiles is not None) or (
        input_file_path is None and molecule_smiles is None
    ):
        console.print(
            "[[red]ERROR[/red]] The `file` and `smiles` arguments are mutually exclusive."
        )
        return

    with handle_common_errors(console) as error_state:
        _submit(
            console=console,
            input_file_path=input_file_path,
            molecule_smiles=molecule_smiles,
            force_field_path=force_field_path,
            spec_name=spec_name,
            spec_file_name=spec_file_name,
        )
        if error_state["has_errored"]:
            return


submit_cli = create_command(
    click_command=click.command("submit"),
    click_options=submit_options(),
    func=_submit_cli,
)
