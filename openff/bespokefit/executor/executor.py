import atexit
import functools
import importlib
import logging
import multiprocessing
import os
import subprocess
import time
from typing import List, Optional, Tuple, Union

import celery
import requests
import rich
from openff.utilities import temporary_cd
from requests import HTTPError
from rich.padding import Padding

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETResponse,
    CoordinatorGETStageStatus,
    CoordinatorPOSTBody,
    CoordinatorPOSTResponse,
)
from openff.bespokefit.executor.services.gateway import launch as launch_gateway
from openff.bespokefit.executor.services.gateway import wait_for_gateway
from openff.bespokefit.executor.utilities.celery import spawn_worker
from openff.bespokefit.executor.utilities.redis import is_redis_available, launch_redis
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema

_logger = logging.getLogger(__name__)


def _base_endpoint():
    return (
        f"http://127.0.0.1:{settings.BEFLOW_GATEWAY_PORT}{settings.BEFLOW_API_V1_STR}/"
    )


def _coordinator_endpoint():
    return f"{_base_endpoint()}{settings.BEFLOW_COORDINATOR_PREFIX}"


class BespokeExecutor:
    """The main class for generating a bespoke set of parameters for molecules based on
    bespoke optimization schemas.
    """

    def __init__(
        self,
        n_fragmenter_workers: int = 1,
        n_qc_compute_workers: int = 1,
        n_optimizer_workers: int = 1,
        directory: Optional[str] = "bespoke-executor",
        launch_redis_if_unavailable: bool = True,
    ):
        """

        Args:
            n_fragmenter_workers: The number of workers that should be launched to
                handle the fragmentation of molecules prior to the generation of QC
                data.
            n_qc_compute_workers: The number of workers that should be launched to
                handle the generation of any QC data.
            n_optimizer_workers: The number of workers that should be launched to
                handle the optimization of the bespoke parameters against any input QC
                data.
            directory: The direction to run in. If ``None``, the executor will run in
                a temporary directory.
            launch_redis_if_unavailable: Whether to launch a redis server if an already
                running one cannot be found.
        """

        self._n_fragmenter_workers = n_fragmenter_workers
        self._n_qc_compute_workers = n_qc_compute_workers
        self._n_optimizer_workers = n_optimizer_workers

        self._directory = directory

        self._launch_redis_if_unavailable = launch_redis_if_unavailable

        self._started = False

        self._gateway_process: Optional[multiprocessing.Process] = None
        self._redis_process: Optional[subprocess.Popen] = None

        self._worker_processes: List[multiprocessing.Process] = []

    def _cleanup_processes(self):

        for worker_process in self._worker_processes:

            if not worker_process.is_alive():
                continue

            worker_process.terminate()
            worker_process.join()

        self._worker_processes = []

        if self._gateway_process is not None and self._gateway_process.is_alive():

            self._gateway_process.terminate()
            self._gateway_process.join()
            self._gateway_process = None

        if self._redis_process is not None and self._redis_process.poll() is None:

            self._redis_process.terminate()
            self._redis_process.wait()
            self._redis_process = None

    def _launch_redis(self):
        """Launches a redis server if an existing one cannot be found."""

        if self._launch_redis_if_unavailable and not is_redis_available(
            host=settings.BEFLOW_REDIS_ADDRESS, port=settings.BEFLOW_REDIS_PORT
        ):
            redis_log_file = open("redis.log", "w")

            self._redis_process = launch_redis(
                settings.BEFLOW_REDIS_PORT,
                redis_log_file,
                redis_log_file,
                terminate_at_exit=False,
            )

    def _launch_workers(self):
        """Launches any service workers if requested."""

        for import_path, n_workers in {
            (settings.BEFLOW_FRAGMENTER_WORKER, self._n_fragmenter_workers),
            (settings.BEFLOW_QC_COMPUTE_WORKER, self._n_qc_compute_workers),
            (settings.BEFLOW_OPTIMIZER_WORKER, self._n_optimizer_workers),
        }:

            if n_workers == 0:
                continue

            worker_module = importlib.import_module(import_path)
            worker_app = getattr(worker_module, "celery_app")

            assert isinstance(worker_app, celery.Celery), "workers must be celery based"

            self._worker_processes.append(
                spawn_worker(worker_app, concurrency=n_workers)
            )

    def start(self, asynchronous=False):
        """Launch the executor, allowing it to receive and run bespoke optimizations.

        Args:
            asynchronous: Whether to run the executor asynchronously.
        """

        if self._started:
            raise RuntimeError("This executor is already running.")

        self._started = True

        if self._directory is not None and len(self._directory) > 0:
            os.makedirs(self._directory, exist_ok=True)

        atexit.register(self._cleanup_processes)

        with temporary_cd(self._directory):

            self._launch_redis()
            self._launch_workers()

        if asynchronous:

            self._gateway_process = multiprocessing.Process(
                target=functools.partial(
                    launch_gateway, directory=self._directory, log_file="gateway.log"
                ),
                daemon=True,
            )
            self._gateway_process.start()

            wait_for_gateway()

        else:

            launch_gateway(self._directory)

    def stop(self):
        """Stop the executor from running and clean ip any associated processes."""

        if not self._started:
            raise RuntimeError("The executor is not running.")

        self._started = False
        self._cleanup_processes()

        atexit.unregister(self._cleanup_processes)

    def submit(
        self, input_schema: BespokeOptimizationSchema
    ) -> CoordinatorPOSTResponse:

        if not self._started:
            raise RuntimeError("The executor is not running.")

        request = requests.post(
            _coordinator_endpoint(),
            data=CoordinatorPOSTBody(input_schema=input_schema).json(),
        )
        request.raise_for_status()

        return CoordinatorPOSTResponse.parse_raw(request.text)

    def __enter__(self):
        self.start(asynchronous=True)
        return self

    def __exit__(self, *args):
        self.stop()


def _query_coordinator(
    optimization_href: str,
) -> Tuple[Optional[CoordinatorGETResponse], Optional[BaseException]]:

    response = None
    error = None

    try:

        coordinator_request = requests.get(optimization_href)
        coordinator_request.raise_for_status()

        response = CoordinatorGETResponse.parse_raw(coordinator_request.text)

    except (ConnectionError, HTTPError) as e:
        error = e

    return None if error is not None else response, error


def _wait_for_stage(
    optimization_href: str, stage_type: str, frequency: Union[int, float] = 5
) -> Tuple[Optional[CoordinatorGETStageStatus], Optional[BaseException]]:

    try:

        while True:

            response, error = _query_coordinator(optimization_href)

            if error is not None:
                return None, error

            stage = {stage.type: stage for stage in response.stages}[stage_type]

            if stage.status in ["errored", "success"]:
                break

            time.sleep(frequency)

    except KeyboardInterrupt:
        return None, None

    return None if error is not None else stage, error


def wait_until_complete(
    optimization_id: str,
    console: Optional["rich.Console"] = None,
    frequency: Union[int, float] = 5,
) -> Optional[CoordinatorGETResponse]:
    """Wait for a specified optimization to complete and return the results.

    Args:
        optimization_id: The unique id of the optimization to wait for.
        console: The console to print to.
        frequency: The frequency (seconds) with which to poll the status of the
            optimization.

    Returns:
        The output of running the optimization.
    """

    console = console if console is not None else rich.get_console()

    optimization_href = f"{_coordinator_endpoint()}/{optimization_id}"

    initial_response, error = _query_coordinator(optimization_href)

    if initial_response is not None:
        stage_types = [stage.type for stage in initial_response.stages]

    else:

        console.log(f"[[red]ERROR[/red]] {str(error)}")
        return None

    stage_messages = {
        "fragmentation": "fragmenting the molecule",
        "qc-generation": "generating bespoke QC data",
        "optimization": "optimizing the parameters",
    }

    for stage_type in stage_types:

        with console.status(stage_messages[stage_type]):

            stage, stage_error = _wait_for_stage(
                optimization_href, stage_type, frequency
            )

        if stage_error is not None:
            console.log(f"[[red]ERROR[/red]] {str(stage_error)}")
            return None

        if stage is None:
            return None

        if stage.status == "errored":

            console.print(f"[[red]x[/red]] {stage_type} failed")
            console.print(Padding(stage.error, (1, 0, 0, 1)))

            break

        console.print(f"[[green]✓[/green]] {stage_type} successful")

    final_response, error = _query_coordinator(optimization_href)

    if error is not None:
        console.log(f"[[red]ERROR[/red]] {str(error)}")
        return None

    return final_response
