import datetime
import hashlib
import json
import uuid
from typing import TYPE_CHECKING, Optional, Union

import click
import click.exceptions
import redis
import rich
from click_option_group import optgroup
from openff.qcsubmit.results import (
    OptimizationResultCollection,
    TorsionDriveResultCollection,
)
from rich import pretty
from rich.padding import Padding
from rich.progress import track
from typing_extensions import Literal

from openff.bespokefit._pydantic import ValidationError, parse_file_as
from openff.bespokefit.cli.utilities import (
    create_command,
    exit_with_messages,
    print_header,
)
from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.services.qcgenerator.cache import _canonicalize_task
from openff.bespokefit.executor.utilities.redis import (
    connect_to_default_redis,
    is_redis_available,
    launch_redis,
)
from openff.bespokefit.schema.data import LocalQCData
from openff.bespokefit.schema.tasks import task_from_result

if TYPE_CHECKING:
    import qcportal


@click.group("cache")
def cache_cli():
    """Commands to manually update the qc data cache."""
    # TODO: do we want the redis database to be saved in a standard location as it is
    #       directory dependent?


def update_from_qcsubmit_options(
    launch_redis_if_unavailable: Optional[bool] = True,
):
    return [
        optgroup("Input Configuration"),
        optgroup.option(
            "--file",
            "input_file_path",
            type=click.Path(exists=True, file_okay=True, dir_okay=False),
            help="The serialised openff-qcsubmit file.",
            default=None,
            required=False,
        ),
        optgroup.option(
            "--qcf-dataset",
            "qcf_dataset_name",
            type=click.STRING,
            help="The name of the dataset in QCFractal to cache locally.",
            required=False,
            default=None,
        ),
        optgroup.option(
            "--qcf-datatype",
            "qcf_datatype",
            type=click.Choice(
                ["torsion", "optimization", "hessian"], case_sensitive=False
            ),
            help="The type of dataset to cache.",
            required=False,
            default="torsion",
            show_default=True,
        ),
        optgroup.option(
            "--qcf-address",
            "qcf_address",
            type=click.STRING,
            help="The address of the QCFractal server to pull the dataset from.",
            default="api.qcarchive.molssi.org:443",
            required=False,
            show_default=True,
        ),
        optgroup.option(
            "--qcf-config",
            "qcf_config",
            type=click.Path(exists=True, file_okay=True, dir_okay=False),
            help="The path to a QCFractal config file containing the address username and password.",
            default=None,
            required=False,
        ),
        optgroup.option(
            "--qcf-spec",
            "qcf_specification",
            type=click.STRING,
            help="The name of the calculation specification in QCFractal.",
            required=False,
            default="default",
            show_default=True,
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


def _update(
    input_file_path: Optional[str],
    qcf_dataset_name: Optional[str],
    qcf_datatype: Literal["torsion", "optimization", "hessian"],
    qcf_address: str,
    qcf_config: Optional[str],
    qcf_specification: str,
    launch_redis_if_unavailable: bool,
):
    """
    The main worker function which updates the redis cache with qcsubmit results objects.
    """

    pretty.install()
    console = rich.get_console()
    print_header(console)

    if (qcf_dataset_name is not None and input_file_path is not None) or (
        qcf_dataset_name is None and input_file_path is None
    ):
        exit_with_messages(
            "[[red]ERROR[/red]] The `file` and `qcf-dataset` arguments are mutually "
            "exclusive",
            console=console,
            exit_code=2,
        )

    console.print(Padding("1. gathering QCSubmit results", (0, 0, 1, 0)))

    if input_file_path is not None:
        qcsubmit_result = _results_from_file(
            console=console, input_file_path=input_file_path
        )
    else:
        client = _connect_to_qcfractal(
            console=console, qcf_address=qcf_address, qcf_config=qcf_config
        )

        qcsubmit_result = _results_from_client(
            client=client,
            console=console,
            qcf_datatype=qcf_datatype,
            qcf_dataset_name=qcf_dataset_name,
            qcf_specification=qcf_specification,
        )

    console.print(Padding("2. connecting to redis cache", (1, 0, 1, 0)))

    settings = current_settings()

    if launch_redis_if_unavailable and not is_redis_available(
        host=settings.BEFLOW_REDIS_ADDRESS, port=settings.BEFLOW_REDIS_PORT
    ):
        redis_log_file = open("redis.log", "w")

        redis_process = launch_redis(
            port=settings.BEFLOW_REDIS_PORT,
            stderr_file=redis_log_file,
            stdout_file=redis_log_file,
            terminate_at_exit=False,
        )
    else:
        redis_process = None

    try:
        redis_connection = connect_to_default_redis()

        # run the update
        _update_from_qcsubmit_result(
            console=console,
            qcsubmit_results=qcsubmit_result,
            redis_connection=redis_connection,
        )
    finally:
        if redis_process is not None:
            # close redis
            console.print(Padding("5. closing redis", (0, 0, 1, 0)))
            redis_process.terminate()
            redis_process.wait()


def _results_from_file(
    console: "rich.Console", input_file_path: str
) -> Union[TorsionDriveResultCollection, OptimizationResultCollection]:
    """
    Try and build a qcsubmit results object from a local file.
    """
    with console.status("loading results file"):
        try:
            qcsubmit_result = parse_file_as(
                Union[TorsionDriveResultCollection, OptimizationResultCollection],
                input_file_path,
            )
            console.print(
                f"[[green]✓[/green]] [repr.filename]{input_file_path}[/repr.filename] "
                f"loaded as a `{qcsubmit_result.__class__.__name__}`."
            )
        except ValidationError as e:
            exit_with_messages(
                Padding(
                    f"[[red]ERROR[/red]] The result file [repr.filename]"
                    f"{input_file_path}[/repr.filename] could not be loaded into "
                    f"QCSubmit"
                ),
                Padding(str(e), (1, 1, 1, 1)),
                console=console,
                exit_code=2,
            )

    return qcsubmit_result


def _connect_to_qcfractal(
    console: "rich.Console",
    qcf_address: str,
    qcf_config: Optional[str],
) -> "qcportal.PortalClient":
    """Connected to the chosen qcfractal server."""
    import qcportal

    with console.status("connecting to qcfractal"):
        try:
            if qcf_config is not None:
                client = qcportal.PortalClient.from_file(config_path=qcf_config)
            else:
                client = qcportal.PortalClient(server_name=qcf_address)
        except BaseException as e:
            exit_with_messages(
                Padding(
                    "[[red]ERROR[/red]] Unable to connect to QCFractal due to the "
                    "following error."
                ),
                Padding(str(e), (1, 1, 1, 1)),
                console=console,
                exit_code=2,
            )

        console.print("[[green]✓[/green]] connected to QCFractal")
        return client


def _results_from_client(
    console: "rich.Console",
    qcf_dataset_name: Optional[str],
    qcf_datatype: Literal["torsion", "optimization", "hessian"],
    client: "qcportal.PortalClient",
    qcf_specification: str,
) -> Union[TorsionDriveResultCollection, OptimizationResultCollection]:
    """Connect to qcfractal and create a qcsubmit results object."""

    with console.status(f"downloading dataset [cyan]{qcf_dataset_name}[/cyan]"):
        if qcf_datatype == "torsion":
            qcsubmit_result = TorsionDriveResultCollection.from_server(
                client=client, datasets=qcf_dataset_name, spec_name=qcf_specification
            )
        elif qcf_datatype == "optimization":
            qcsubmit_result = OptimizationResultCollection.from_server(
                client=client, datasets=qcf_dataset_name, spec_name=qcf_specification
            )
        else:
            raise NotImplementedError()

        console.print("[[green]✓[/green]] dataset downloaded")

    return qcsubmit_result


def _update_from_qcsubmit_result(
    console: "rich.Console",
    qcsubmit_results: Union[TorsionDriveResultCollection, OptimizationResultCollection],
    redis_connection: redis.Redis,
):
    """Update the qcgeneration redis cache using qcsubmit results objects."""

    # process the results into local data
    console.print(Padding("3. updating local cache", (0, 0, 1, 0)))

    with console.status("building local results"):
        try:
            local_data = LocalQCData.from_remote_records(
                qc_records=qcsubmit_results.to_records()
            )
            console.print("[[green]✓[/green]] local results built")
        except BaseException as e:
            exit_with_messages(
                Padding(
                    "[[red]ERROR[/red]] The local results could not be built due to the "
                    "following error.",
                    (1, 0, 0, 0),
                ),
                Padding(str(e), (1, 1, 1, 1)),
                console=console,
                exit_code=2,
            )

    new_results = 0
    for result in track(
        local_data.qc_records, description="[green]Processing results..."
    ):
        task = task_from_result(result=result)
        con_task = _canonicalize_task(task=task)
        task_hash = hashlib.sha512(con_task.json().encode()).hexdigest()
        task_id = redis_connection.hget("qcgenerator:task-ids", task_hash)

        if task_id is None:
            # we need to add the result with a random id
            task_id = str(uuid.uuid4())
            redis_connection.hset("qcgenerator:types", task_id, task.type)
            redis_connection.hset("qcgenerator:task-ids", task_hash, task_id)
            # mock a celery worker result
            task_meta = {
                "status": "SUCCESS",
                "result": result.json(),
                "traceback": None,
                "children": [],
                "date_done": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"),
                "task_id": task_id,
            }
            redis_connection.set(f"celery-task-meta-{task_id}", json.dumps(task_meta))
            new_results += 1

    console.print(
        f"[[green]✓[/green]] [blue]{new_results}[/blue]/[cyan]{len(local_data.qc_records)}[/cyan] results cached"
    )

    console.print(Padding("4. saving local cache", (1, 0, 1, 0)))
    # block until data is saved
    redis_connection.save()


update_cli = create_command(
    click_command=click.command("update"),
    click_options=update_from_qcsubmit_options(),
    func=_update,
)


cache_cli.add_command(update_cli)
