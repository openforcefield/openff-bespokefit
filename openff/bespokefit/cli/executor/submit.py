import os.path
from typing import TYPE_CHECKING, Optional, Tuple

import click
import click.exceptions
import rich
from click_option_group import optgroup
from openff.utilities import get_data_file_path
from pydantic import ValidationError
from rich import pretty
from rich.padding import Padding

from openff.bespokefit.cli.utilities import (
    create_command,
    exit_with_messages,
    print_header,
)
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
            "--workflow",
            "workflow_name",
            type=click.Choice(choices=["default", "debug"], case_sensitive=False),
            help="The name of the built-in bespoke fitting workflow to use.",
            required=False,
        ),
        click.option(
            "--workflow-file",
            "workflow_file_name",
            type=click.Path(exists=False, file_okay=True, dir_okay=False),
            help="The path to a serialized bespoke workflow factory that encodes the "
            "bespoke fitting workflow to use.",
            required=False,
        ),
        optgroup.group("Workflow overrides"),
        optgroup.option(
            "--force-field",
            "force_field_path",
            type=click.Path(exists=False, file_okay=True, dir_okay=False),
            help="A custom initial force field to start the bespoke fits from.",
            required=False,
        ),
        optgroup.option(
            "--target-torsion",
            "target_torsion_smirks",
            type=str,
            help="The SMIRKS pattern(s) that should be used to identify the **bonds** "
            "in the input molecule to generate bespoke torsions around if requested. It "
            "must only match the two atoms involved in the central bond. This argument "
            "can be specified multiple times if you wish to provide multiple patterns.",
            required=False,
            multiple=True,
        ),
    ]


def _to_input_schema(
    console: "rich.Console",
    molecule: "Molecule",
    force_field_path: Optional[str],
    target_torsion_smirks: Tuple[str],
    workflow_name: Optional[str],
    workflow_file_name: Optional[str],
) -> "BespokeOptimizationSchema":

    from openff.bespokefit.workflows.bespoke import BespokeWorkflowFactory

    if (workflow_name is not None and workflow_file_name is not None) or (
        workflow_name is None and workflow_file_name is None
    ):

        exit_with_messages(
            "[[red]ERROR[/red] The `--workflow` and `--workflow-file` arguments are "
            "mutually exclusive",
            console=console,
            exit_code=2,
        )

    invalid_workflow_name = (
        workflow_name if workflow_name is not None else workflow_file_name
    )

    try:

        if workflow_name is not None:

            workflow_file_name = get_data_file_path(
                os.path.join("schemas", f"{workflow_name.lower()}.json"),
                "openff.bespokefit",
            )

        workflow_factory = BespokeWorkflowFactory.from_file(workflow_file_name)

        if force_field_path is not None:
            workflow_factory.initial_force_field = force_field_path
        if len(target_torsion_smirks) > 0:
            workflow_factory.target_torsion_smirks = [*target_torsion_smirks]

    except (FileNotFoundError, RuntimeError) as e:

        # Need for QCSubmit #176
        if isinstance(e, RuntimeError) and "could not be found" not in str(e):
            raise e

        exit_with_messages(
            Padding(
                f"[[red]ERROR[/red]] The specified workflow could not be found: "
                f"[repr.filename]{invalid_workflow_name}[/repr.filename]",
                (1, 0, 0, 0),
            ),
            console=console,
            exit_code=2,
        )

    except ValidationError as e:

        exit_with_messages(
            Padding(
                f"[[red]ERROR[/red]] The workflow could not be parsed. Make sure "
                f"[repr.filename]{invalid_workflow_name}[/repr.filename] is a valid "
                f"`BespokeWorkflowFactory` schema.",
                (1, 0, 0, 0),
            ),
            Padding(str(e), (1, 1, 1, 1)),
            console=console,
            exit_code=2,
        )

    else:
        return workflow_factory.optimization_schema_from_molecule(molecule)


def _submit(
    console: "rich.Console",
    input_file_path: Optional[str],
    molecule_smiles: Optional[str],
    force_field_path: Optional[str],
    target_torsion_smirks: Tuple[str],
    workflow_name: Optional[str],
    workflow_file_name: Optional[str],
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

        exit_with_messages(
            "[[red]ERROR[/red]] only one molecule can currently be submitted at "
            "a time",
            console=console,
            exit_code=2,
        )

    console.print("[[green]✓[/green]] [blue]1[/blue] molecule was found")

    with console.status("building fitting schemas"):

        input_schema = _to_input_schema(
            console,
            molecule,
            force_field_path,
            target_torsion_smirks,
            workflow_name,
            workflow_file_name,
        )

    console.print("[[green]✓[/green]] fitting schema generated")

    console.print(Padding("2. submitting the workflow", (1, 0, 1, 0)))

    response_id = BespokeExecutor.submit(input_schema)
    console.print(f"[[green]✓[/green]] workflow submitted: id={response_id}")

    return response_id


def _submit_cli(
    input_file_path: Optional[str],
    molecule_smiles: Optional[str],
    force_field_path: Optional[str],
    target_torsion_smirks: Tuple[str],
    workflow_name: Optional[str],
    workflow_file_name: Optional[str],
):
    """Submit a new bespoke optimization to a running executor."""

    pretty.install()

    console = rich.get_console()
    print_header(console)

    if (input_file_path is not None and molecule_smiles is not None) or (
        input_file_path is None and molecule_smiles is None
    ):
        exit_with_messages(
            "[[red]ERROR[/red]] The `file` and `smiles` arguments are mutually "
            "exclusive.",
            console=console,
            exit_code=2,
        )

    with handle_common_errors(console) as error_state:

        _submit(
            console=console,
            input_file_path=input_file_path,
            molecule_smiles=molecule_smiles,
            force_field_path=force_field_path,
            target_torsion_smirks=target_torsion_smirks,
            workflow_name=workflow_name,
            workflow_file_name=workflow_file_name,
        )

    if error_state["has_errored"]:
        raise click.exceptions.Exit(code=2)


submit_cli = create_command(
    click_command=click.command("submit"),
    click_options=submit_options(),
    func=_submit_cli,
)
