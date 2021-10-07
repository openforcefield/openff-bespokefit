import time
from typing import Optional

import click
import rich
from click_option_group import optgroup
from rich import pretty

from openff.bespokefit.cli.utilities import create_command, print_header


# The run command inherits these options so be sure to take that into account when
# making changes here.
def launch_options(
    directory: str = "bespoke-executor",
    n_fragmenter_workers: Optional[int] = None,
    n_qc_compute_workers: Optional[int] = None,
    n_optimizer_workers: Optional[int] = None,
    launch_redis_if_unavailable: Optional[bool] = True,
):

    return [
        optgroup("Executor configuration"),
        optgroup.option(
            "--directory",
            type=click.Path(exists=False, file_okay=False, dir_okay=True),
            help="The directory to store any working and log files in",
            required=True,
            default=directory,
            show_default=directory is not None,
        ),
        optgroup.group("Worker configuration"),
        optgroup.option(
            "--n-fragmenter-workers",
            "n_fragmenter_workers",
            type=click.INT,
            help="The number of fragmentation workers to spawn",
            required=n_fragmenter_workers is None,
            default=n_fragmenter_workers,
            show_default=n_fragmenter_workers is not None,
        ),
        optgroup.option(
            "--n-qc-compute-workers",
            "n_qc_compute_workers",
            type=click.INT,
            help="The number of QC compute workers to spawn",
            required=n_qc_compute_workers is None,
            default=n_qc_compute_workers,
            show_default=n_qc_compute_workers is not None,
        ),
        optgroup.option(
            "--n-optimizer-workers",
            "n_optimizer_workers",
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


def _launch_cli(
    directory: str,
    n_fragmenter_workers: int,
    n_qc_compute_workers: int,
    n_optimizer_workers: int,
    launch_redis_if_unavailable: bool,
):
    """Launch a bespoke executor."""

    pretty.install()

    console = rich.get_console()
    print_header(console)

    from openff.bespokefit.executor import BespokeExecutor

    executor_status = console.status("launching the bespoke executor")
    executor_status.start()

    with BespokeExecutor(
        directory=directory,
        n_fragmenter_workers=n_fragmenter_workers,
        n_qc_compute_workers=n_qc_compute_workers,
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
