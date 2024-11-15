import os.path
from typing import TYPE_CHECKING, List, Optional, Tuple

import click
import click.exceptions
import rich
from click_option_group import optgroup
from openff.utilities import get_data_file_path
from rich import pretty
from rich.padding import Padding
from rich.progress import track
from rich.table import Table

from openff.bespokefit._pydantic import ValidationError
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
def submit_options(allow_multiple_molecules: bool = False):
    return [
        click.option(
            "--file",
            "input_file_path",
            type=click.Path(exists=True, file_okay=True, dir_okay=False),
            help="The file containing the molecule of interest",
            required=False,
            multiple=allow_multiple_molecules,
        ),
        click.option(
            "--smiles",
            "molecule_smiles",
            type=click.STRING,
            help="The SMILES string representation of the input molecule.",
            required=False,
            multiple=allow_multiple_molecules,
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
        optgroup.option(
            "--default-qc-spec",
            type=(str, str, str),
            help="The program, method, and basis to use by default when performing any "
            "QC calculations, e.g. `--default-qc-spec xtb gfn2xtb none`. If no basis "
            "is required to be specified for a particular method (e.g. for ANI or XTB) "
            "then 'none' should be specified.",
            required=False,
        ),
    ]


def _to_input_schema(
    console: "rich.Console",
    molecule: "Molecule",
    force_field_path: Optional[str],
    target_torsion_smirks: Tuple[str],
    default_qc_spec: Optional[Tuple[str, str, str]],
    workflow_name: Optional[str],
    workflow_file_name: Optional[str],
) -> "BespokeOptimizationSchema":
    from openff.qcsubmit.common_structures import QCSpec, QCSpecificationError

    from openff.bespokefit.workflows.bespoke import BespokeWorkflowFactory

    if (workflow_name is not None and workflow_file_name is not None) or (
        workflow_name is None and workflow_file_name is None
    ):
        exit_with_messages(
            "[[red]ERROR[/red]] The `--workflow` and `--workflow-file` arguments are "
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
        if default_qc_spec is not None:
            program, method, basis = default_qc_spec

            if basis.lower() == "none":
                basis = None

            workflow_factory.default_qc_specs = [
                QCSpec(
                    program=program,
                    method=method,
                    basis=basis,
                    spec_description="CLI provided spec",
                )
            ]

    except FileNotFoundError:
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

    except QCSpecificationError as e:
        exit_with_messages(
            Padding(
                f"[[red]ERROR[/red]] The QCSpecification is not valid. Make sure you have supplied a valid combination "
                f"of program: {program}, method: {method}, and basis: {basis}",
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
    input_file_path: Optional[List[str]],
    molecule_smiles: Optional[List[str]],
    force_field_path: Optional[str],
    target_torsion_smirks: Tuple[str],
    default_qc_spec: Optional[Tuple[str, str, str]],
    workflow_name: Optional[str],
    workflow_file_name: Optional[str],
    allow_multiple_molecules: bool,
    save_submission: bool,
) -> List[str]:
    from openff.toolkit.topology import Molecule

    from openff.bespokefit.executor import BespokeFitClient
    from openff.bespokefit.executor.services import current_settings

    settings = current_settings()
    client = BespokeFitClient(settings=settings)

    console.print(Padding("1. preparing the bespoke workflow", (0, 0, 1, 0)))

    all_molecules = []

    if input_file_path:
        with console.status("loading the molecules"):
            for input_file in input_file_path:
                file_molecules = Molecule.from_file(input_file)
                if isinstance(file_molecules, Molecule):
                    file_molecules = [file_molecules]

                for m in file_molecules:
                    m.properties["input_file"] = input_file
                all_molecules.extend(file_molecules)

    if molecule_smiles:
        with console.status("creating molecule from smiles"):
            all_molecules.extend(
                [Molecule.from_smiles(smiles) for smiles in molecule_smiles]
            )

    if not allow_multiple_molecules and len(all_molecules) > 1:
        exit_with_messages(
            "[[red]ERROR[/red]] only one molecule can be submitted at once",
            console=console,
            exit_code=2,
        )

    for molecule in all_molecules:
        if "." in molecule.to_smiles():
            exit_with_messages(
                f"[[red]ERROR[/red]] complexes are not supported, {molecule} can not be submitted!",
                console=console,
                exit_code=2,
            )

    console.print(
        f"[[green]✓[/green]] [blue]{len(all_molecules)}[/blue] molecules found"
    )

    input_schemas = []
    for molecule in track(
        all_molecules,
        description="building fitting schemas",
        console=console,
        transient=True,
        total=len(all_molecules),
    ):
        input_schemas.append(
            _to_input_schema(
                console,
                molecule,
                force_field_path,
                target_torsion_smirks,
                default_qc_spec,
                workflow_name,
                workflow_file_name,
            )
        )

    console.print("[[green]✓[/green]] fitting schemas generated")

    console.print(Padding("2. submitting the workflow", (1, 0, 1, 0)))
    response_ids = []
    for input_schema in track(
        input_schemas,
        description="submitting tasks",
        total=len(input_schemas),
        transient=True,
        console=console,
    ):
        response_ids.append(client.submit_optimization(input_schema=input_schema))

    console.print("[[green]✓[/green]] the following workflows were submitted")
    table = Table()
    table.add_column("ID", justify="center", no_wrap=True)
    table.add_column("SMILES", overflow="fold")
    table.add_column("NAME", overflow="fold")
    table.add_column("FILE", no_wrap=True)

    for molecule, response_id in zip(all_molecules, response_ids):
        table.add_row(
            response_id,
            # Brackets around things like [nH] will sometimes be interpreted as formatting characters
            # by rich, so use rich.markup.escape to avoid mangling the SMILES.
            # See https://github.com/openforcefield/openff-bespokefit/issues/319
            rich.markup.escape(
                molecule.to_smiles(explicit_hydrogens=False, mapped=False)
            ),
            molecule.name,
            molecule.properties.get("input_file", ""),
        )

    console.print(table)

    if save_submission:
        # also write the data to a csv file
        import csv

        with open("submission.csv", "w", newline="") as csv_file:
            csv_table = csv.writer(csv_file)
            csv_table.writerow(["ID", "SMILES", "NAME", "FILE"])
            for molecule, response_id in zip(all_molecules, response_ids):
                csv_table.writerow(
                    [
                        response_id,
                        molecule.to_smiles(explicit_hydrogens=False, mapped=False),
                        molecule.name,
                        molecule.properties.get("input_file", ""),
                    ]
                )

    return response_ids


def _submit_cli(
    input_file_path: Optional[List[str]],
    molecule_smiles: Optional[List[str]],
    force_field_path: Optional[List[str]],
    target_torsion_smirks: Tuple[str],
    default_qc_spec: Optional[Tuple[str, str, str]],
    workflow_name: Optional[str],
    workflow_file_name: Optional[str],
    save_submission: bool,
):
    """Submit a new bespoke optimization to a running executor."""

    pretty.install()

    console = rich.get_console()
    print_header(console)

    with handle_common_errors(console) as error_state:
        _submit(
            console=console,
            input_file_path=input_file_path,
            molecule_smiles=molecule_smiles,
            force_field_path=force_field_path,
            target_torsion_smirks=target_torsion_smirks,
            default_qc_spec=default_qc_spec,
            workflow_name=workflow_name,
            workflow_file_name=workflow_file_name,
            allow_multiple_molecules=True,
            save_submission=save_submission,
        )

    if error_state["has_errored"]:
        raise click.exceptions.Exit(code=2)


__submit_options = [*submit_options(allow_multiple_molecules=True)]
__submit_options.insert(
    4,
    click.option(
        "--save-submission-info/--no-save-submission-info",
        "save_submission",
        help="If the submission table printed in the terminal, which maps input molecules to an optimization ID, should be saved to a csv file.",
        default=False,
    ),
)

submit_cli = create_command(
    click_command=click.command("submit"),
    click_options=__submit_options,
    func=_submit_cli,
)
