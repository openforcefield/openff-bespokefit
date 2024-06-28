import click

worker_types = ["fragmenter", "qc-compute", "optimizer"]


@click.command("launch-worker")
@click.option(
    "--worker-type",
    type=click.Choice(worker_types),
    help="The type of bespokefit worker to launch",
    required=True,
)
def worker_cli(worker_type: str):
    """
    Launch a single worker of the requested type in the main process.

    Used to connect workers to a remote bespokefit server.

    Note:

        By default bespokefit will automatically use all cores and memory made available to the worker which should
        be declared in the job submission script. To change these defaults see the settings `BEFLOW_QC_COMPUTE_WORKER_N_CORES` &
        `BEFLOW_QC_COMPUTE_WORKER_MAX_MEM`.

    Args:

        worker_type: The alias name of the worker type which should be started.
    """
    import importlib

    import rich
    from rich import pretty

    from openff.bespokefit.cli.utilities import print_header
    from openff.bespokefit.executor.services import current_settings
    from openff.bespokefit.executor.utilities.celery import spawn_worker

    pretty.install()

    console = rich.get_console()
    print_header(console)

    worker_status = console.status(f"launching {worker_type} worker")
    worker_status.start()

    settings = current_settings()

    worker_kwargs = {}

    if worker_type == "fragmenter":
        worker_settings = settings.fragmenter_settings
    elif worker_type == "qc-compute":
        worker_settings = settings.qc_compute_settings
        worker_kwargs["pool"] = "solo"
    else:
        worker_settings = settings.optimizer_settings

    worker_module = importlib.import_module(worker_settings.import_path)
    importlib.reload(worker_module)
    worker_app = getattr(worker_module, "celery_app")

    worker_status.stop()
    console.print(f"[[green]✓[/green]] bespoke {worker_type} worker launched")

    spawn_worker(worker_app, concurrency=1, asynchronous=False, **worker_kwargs)
