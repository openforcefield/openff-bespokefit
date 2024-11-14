import click


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
    required=False,
)
@click.option(
    "--force-field",
    "force_field_path",
    type=click.Path(exists=False, file_okay=True, dir_okay=False),
    help="The path to save the force field to ",
    required=False,
)
def retrieve_cli(optimization_id, output_file_path, force_field_path):
    """Retrieve the current output of a bespoke optimization."""
    import click.exceptions
    import rich
    from rich import pretty
    from rich.padding import Padding

    from openff.bespokefit.cli.utilities import print_header
    from openff.bespokefit.executor.utilities import handle_common_errors

    pretty.install()

    console = rich.get_console()
    print_header(console)

    if output_file_path is None and force_field_path is None:
        raise click.UsageError(
            "At least one of the `--output` and `--force-field` flags should be "
            "specified."
        )

    from openff.bespokefit.executor import BespokeFitClient
    from openff.bespokefit.executor.services import current_settings

    settings = current_settings()
    client = BespokeFitClient(settings=settings)

    with handle_common_errors(console) as error_state:
        results = client.get_optimization(optimization_id=optimization_id)
    if error_state["has_errored"]:
        raise click.exceptions.Exit(code=2)

    message = "the bespoke fit is"

    if results.status == "waiting":
        console.print(f"[[grey]⧖[/grey]] {message} queued")
    elif results.status == "running":
        console.print(f"[[yellow]↻[/yellow]] {message} running")
    elif results.status == "errored":
        console.print(f"[[red]x[/red]] {message} errored")
        console.print(Padding(results.error, (1, 1, 1, 1)))
    elif results.status == "success":
        console.print(f"[[green]✓[/green]] {message} finished")
    else:
        raise NotImplementedError()

    if output_file_path is not None:
        console.print(
            Padding(
                f"outputs have been saved to "
                f"[repr.filename]{output_file_path}[/repr.filename]",
                (1, 0, 1, 0),
            )
        )

        with open(output_file_path, "w") as file:
            file.write(results.json())

    if force_field_path is not None:
        message = Padding(
            (
                (
                    f"the bespoke fit {'failed' if results.error else 'is still running'} "
                    f"and so no force field will be saved"
                )
                if not results.bespoke_force_field
                else (
                    f"the bespoke force field has been saved to "
                    f"[repr.filename]{force_field_path}[/repr.filename]"
                )
            ),
            (1, 0, 1, 0),
        )

        if results.bespoke_force_field:
            results.bespoke_force_field.to_file(force_field_path)

        console.print(message)
