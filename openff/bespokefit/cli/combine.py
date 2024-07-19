import copy
from typing import List, Optional

import click
import rich
from openff.toolkit import ForceField
from openff.toolkit.utils.exceptions import ParameterLookupError
from rich import pretty
from rich.padding import Padding

from openff.bespokefit.cli.utilities import exit_with_messages, print_header
from openff.bespokefit.executor.utilities import handle_common_errors


@click.command("combine")
@click.option(
    "--output",
    "output_file",
    type=click.STRING,
    help="The name of the file the combined force field should be wrote to.",
    required=True,
)
@click.option(
    "--ff",
    "force_field_files",
    type=click.Path(exists=True, dir_okay=False),
    help="The file name of any local force fields to include in the combined force field.",
    required=False,
    multiple=True,
)
@click.option(
    "--id",
    "task_ids",
    type=click.STRING,
    help="The task ids from which the final force field should be added to the combined force field.",
    required=False,
    multiple=True,
)
def combine_cli(
    output_file: str,
    force_field_files: Optional[List[str]],
    task_ids: Optional[List[str]],
):
    """
    Combine force fields from local files and task ids.
    """
    pretty.install()

    console = rich.get_console()
    print_header(console)

    if not force_field_files and not task_ids:
        exit_with_messages(
            "[[red]ERROR[/red]] At least one of the `--ff` or `--id` should be specified",
            console=console,
            exit_code=2,
        )

    all_force_fields = []

    if force_field_files:
        all_force_fields.extend(
            [
                ForceField(
                    force_field, load_plugins=True, allow_cosmetic_attributes=True
                )
                for force_field in force_field_files
            ]
        )

    if task_ids:
        from openff.bespokefit.executor import BespokeFitClient
        from openff.bespokefit.executor.services import current_settings

        client = BespokeFitClient(settings=current_settings())

        with handle_common_errors(console) as error_state:
            results = [client.get_optimization(task_id) for task_id in task_ids]
        if error_state["has_errored"]:
            raise click.exceptions.Exit(code=2)

        all_force_fields.extend([result.bespoke_force_field for result in results])

    # Now combine all unique torsions
    master_ff = copy.deepcopy(all_force_fields[0])
    for ff in all_force_fields[1:]:
        for parameter in ff.get_parameter_handler("ProperTorsions").parameters:
            try:
                _ = master_ff.get_parameter_handler("ProperTorsions")[parameter.smirks]
            except ParameterLookupError:
                master_ff.get_parameter_handler("ProperTorsions").add_parameter(
                    parameter=parameter
                )

    master_ff.to_file(filename=output_file, discard_cosmetic_attributes=True)

    message = Padding(
        f"The combined force field has been saved to [repr.filename]{output_file}[/repr.filename]",
        (1, 0, 1, 0),
    )
    console.print(message)
