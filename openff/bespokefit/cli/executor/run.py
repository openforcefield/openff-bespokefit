from typing import Optional, Tuple

import click
import click.exceptions
import rich
from rich import pretty
from rich.padding import Padding

from openff.bespokefit.cli.executor.launch import (
    launch_options,
    validate_redis_connection,
)
from openff.bespokefit.cli.executor.submit import _submit, submit_options
from openff.bespokefit.cli.utilities import create_command, print_header


def _run_cli(
    input_file_path: Optional[str],
    molecule_smiles: Optional[str],
    output_file_path: str,
    output_force_field_path: Optional[str],
    force_field_path: Optional[str],
    target_torsion_smirks: Tuple[str],
    default_qc_spec: Optional[Tuple[str, str, str]],
    workflow_name: Optional[str],
    workflow_file_name: Optional[str],
    directory: Optional[str],
    n_fragmenter_workers: int,
    n_qc_compute_workers: int,
    qc_compute_n_cores: Optional[int],
    qc_compute_max_mem: Optional[float],
    n_optimizer_workers: int,
    launch_redis_if_unavailable: bool,
):
    """Run bespoke optimization using a temporary executor.

    If you are running many bespoke optimizations it is recommended that you first launch
    a bespoke executor using the `launch` command and then submit the optimizations to it
    using the `submit` command.
    """

    pretty.install()

    console = rich.get_console()
    print_header(console)

    from openff.bespokefit.executor import (
        BespokeExecutor,
        BespokeFitClient,
        BespokeWorkerConfig,
    )
    from openff.bespokefit.executor.services import current_settings
    from openff.bespokefit.executor.utilities import handle_common_errors

    executor_status = console.status("launching the bespoke executor")
    executor_status.start()

    validate_redis_connection(console, allow_existing=False)
    settings = current_settings()
    client = BespokeFitClient(settings=settings)

    with BespokeExecutor(
        directory=directory,
        n_fragmenter_workers=n_fragmenter_workers,
        n_qc_compute_workers=n_qc_compute_workers,
        qc_compute_worker_config=BespokeWorkerConfig(
            n_cores="auto" if not qc_compute_n_cores else qc_compute_n_cores,
            max_memory="auto" if not qc_compute_max_mem else qc_compute_max_mem,
        ),
        n_optimizer_workers=n_optimizer_workers,
        launch_redis_if_unavailable=launch_redis_if_unavailable,
    ):
        executor_status.stop()
        console.print("[[green]✓[/green]] bespoke executor launched")
        console.line()

        with handle_common_errors(console) as error_state:
            response_id = _submit(
                console=console,
                input_file_path=(
                    [input_file_path] if input_file_path is not None else []
                ),
                molecule_smiles=(
                    [molecule_smiles] if molecule_smiles is not None else []
                ),
                force_field_path=force_field_path,
                target_torsion_smirks=target_torsion_smirks,
                default_qc_spec=default_qc_spec,
                workflow_name=workflow_name,
                workflow_file_name=workflow_file_name,
                allow_multiple_molecules=False,
                save_submission=False,
            )

            console.print(Padding("3. running the fitting pipeline", (1, 0, 1, 0)))

            results = client.wait_until_complete(
                optimization_id=response_id[0], console=console
            )

            console.print(
                Padding(
                    f"outputs have been saved to "
                    f"[repr.filename]{output_file_path}[/repr.filename]",
                    (1, 0, 1, 0),
                )
            )

            with open(output_file_path, "w") as file:
                file.write(results.json())

            if output_force_field_path and results.bespoke_force_field is not None:
                console.print(
                    Padding(
                        f"the bespoke force field has been saved to "
                        f"[repr.filename]{output_force_field_path}[/repr.filename]",
                        (0, 0, 1, 0),
                    )
                )

                results.bespoke_force_field.to_file(output_force_field_path)

        if error_state["has_errored"] or results.status == "errored":
            raise click.exceptions.Exit(code=2)


__run_options = [*submit_options(allow_multiple_molecules=False)]
__run_options.insert(
    4,
    click.option(
        "--output",
        "output_file_path",
        type=click.Path(exists=False, file_okay=True, dir_okay=False),
        help="The path [.json] to save the full results to",
        default="output.json",
        show_default=True,
    ),
)
__run_options.insert(
    5,
    click.option(
        "--output-force-field",
        "output_force_field_path",
        type=click.Path(exists=False, file_okay=True, dir_okay=False),
        help="The (optional) path [.offxml] to save the bespoke force field to if the "
        "fit succeeded",
        required=False,
    ),
)
__run_options.extend(launch_options(directory=None))

run_cli = create_command(
    click_command=click.command("run"), click_options=__run_options, func=_run_cli
)
