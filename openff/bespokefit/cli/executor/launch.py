import time
from typing import Optional

import click
import rich
from click_option_group import optgroup
from rich import pretty
from rich.padding import Padding

from openff.bespokefit.cli.utilities import (
    create_command,
    exit_with_messages,
    print_header,
)


# The run command inherits these options so be sure to take that into account when
# making changes here.
def launch_options(
    directory: Optional[str] = "bespoke-executor",
    n_fragmenter_workers: Optional[int] = 1,
    n_qc_compute_workers: Optional[int] = 1,
    n_optimizer_workers: Optional[int] = 1,
    launch_redis_if_unavailable: Optional[bool] = True,
):
    return [
        optgroup("Executor configuration"),
        optgroup.option(
            "--directory",
            type=click.Path(exists=False, file_okay=False, dir_okay=True),
            help="The directory to store any working and log files in"
            + (
                ""
                if directory is not None
                else (
                    ". By default all files and logs will be stored in a temporary "
                    "directory and deleted when the command exists."
                )
            ),
            required=directory is not None,
            default=directory,
            show_default=directory is not None,
        ),
        optgroup.group("Worker configuration"),
        optgroup.option(
            "--n-fragmenter-workers",
            type=click.INT,
            help="The number of fragmentation workers to spawn",
            required=n_fragmenter_workers is None,
            default=n_fragmenter_workers,
            show_default=n_fragmenter_workers is not None,
        ),
        optgroup.option(
            "--n-qc-compute-workers",
            type=click.INT,
            help="The number of QC compute workers to spawn",
            required=n_qc_compute_workers is None,
            default=n_qc_compute_workers,
            show_default=n_qc_compute_workers is not None,
        ),
        optgroup.option(
            "--qc-compute-n-cores",
            type=click.INT,
            help="The maximum number of cores ( / CPUs) to reserve *per* QC compute "
            "worker. The actual number of cores utilised will depend on the type of QC "
            "calculation being performed. If no value is specified, all CPUs will be "
            "made available to each worker.",
            required=False,
        ),
        optgroup.option(
            "--qc-compute-max-mem",
            type=click.FLOAT,
            help="The maximum memory in GB available to *each* core of *each* QC "
            "worker. If no value is specified, the full machine memory will be made "
            "available to each worker.",
            required=False,
        ),
        optgroup.option(
            "--n-optimizer-workers",
            type=click.INT,
            help="The number of optimizer workers to spawn",
            required=n_optimizer_workers is None,
            default=n_optimizer_workers,
            show_default=n_optimizer_workers is not None,
        ),
        optgroup.group("Storage configuration"),
        optgroup.option(
            "--launch-redis/--no-launch-redis",
            "launch_redis_if_unavailable",
            help="Whether to launch a redis server if an already running one cannot be "
            "found.",
            required=launch_redis_if_unavailable is None,
            default=launch_redis_if_unavailable,
            show_default=launch_redis_if_unavailable is not None,
        ),
    ]


def validate_redis_connection(console: "rich.Console", allow_existing: bool = True):
    """Checks whether a redis server is already running and if so, that it is
    compatible with BespokeFit.
    """

    from openff.bespokefit.executor.services import current_settings
    from openff.bespokefit.executor.utilities.redis import (
        RedisBadConfigurationError,
        RedisNotConfiguredError,
        connect_to_default_redis,
        is_redis_available,
    )

    settings = current_settings()

    if not is_redis_available(
        host=settings.BEFLOW_REDIS_ADDRESS, port=settings.BEFLOW_REDIS_PORT
    ):
        return

    if not allow_existing:
        exit_with_messages(
            f"[[red]ERROR[/red]] a redis server is already running at "
            f"host={settings.BEFLOW_REDIS_ADDRESS} and "
            f"port={settings.BEFLOW_REDIS_PORT}, continuing to run would likely cause"
            f"unintended consequences.",
            console=console,
            exit_code=1,
        )

    console.print(
        Padding(
            "[[yellow]WARNING[/yellow]] a redis server is already running - this "
            "will be connected to by default",
            (0, 0, 1, 0),
        )
    )

    try:
        connect_to_default_redis()
    except (RedisNotConfiguredError, RedisBadConfigurationError) as e:
        exit_with_messages(
            f"[[red]ERROR[/red]] {str(e)}",
            console=console,
            exit_code=1,
        )


def _launch_cli(
    directory: str,
    n_fragmenter_workers: int,
    n_qc_compute_workers: int,
    qc_compute_n_cores: Optional[int],
    qc_compute_max_mem: Optional[float],
    n_optimizer_workers: int,
    launch_redis_if_unavailable: bool,
):
    """Launch a bespoke executor."""

    pretty.install()

    console = rich.get_console()
    print_header(console)

    from openff.bespokefit.executor import BespokeExecutor, BespokeWorkerConfig

    executor_status = console.status("launching the bespoke executor")
    executor_status.start()

    validate_redis_connection(console)

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

        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            pass


launch_cli = create_command(
    click_command=click.command("launch"),
    click_options=launch_options(),
    func=_launch_cli,
)
