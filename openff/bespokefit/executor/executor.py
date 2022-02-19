import atexit
import functools
import importlib
import logging
import multiprocessing
import os
import shutil
import subprocess
import time
from tempfile import mkdtemp
from typing import List, Optional, Type, TypeVar, Union

import celery
import requests
import rich
from openff.toolkit.typing.engines.smirnoff import ForceField
from openff.utilities import temporary_cd
from pydantic import Field
from rich.padding import Padding
from typing_extensions import Literal

from openff.bespokefit.executor.services import Settings, settings
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
from openff.bespokefit.executor.utilities.typing import Status
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults
from openff.bespokefit.utilities.pydantic import BaseModel

_T = TypeVar("_T")

_logger = logging.getLogger(__name__)


def _base_endpoint():
    return (
        f"http://127.0.0.1:{settings.BEFLOW_GATEWAY_PORT}{settings.BEFLOW_API_V1_STR}/"
    )


def _coordinator_endpoint():
    return f"{_base_endpoint()}{settings.BEFLOW_COORDINATOR_PREFIX}"


class BespokeWorkerConfig(BaseModel):
    """Configuration options for a bespoke executor worker."""

    n_cores: Union[int, Literal["auto"]] = Field(
        1,
        description="The maximum number of cores to reserve for this worker to "
        "parallelize tasks, such as QC chemical calculations, across.",
    )
    max_memory: Union[float, Literal["auto"]] = Field(
        "auto",
        description="A guideline for the total maximum memory in GB **per core** that "
        "is available for this worker. This number may be ignored depending on the "
        "task type.",
    )


class BespokeExecutorStageOutput(BaseModel):
    """A model that stores the output of a particular stage in the bespoke fitting
    workflow e.g. QC data generation."""

    type: str = Field(..., description="The type of stage.")

    status: Status = Field(..., description="The status of the stage.")

    error: Optional[str] = Field(
        ..., description="The error, if any, raised by the stage."
    )


class BespokeExecutorOutput(BaseModel):
    """A model that stores the current output of running bespoke fitting workflow
    including any partial or final results."""

    smiles: str = Field(
        ...,
        description="The SMILES representation of the molecule that the bespoke "
        "parameters are being generated for.",
    )

    stages: List[BespokeExecutorStageOutput] = Field(
        ..., description="The outputs from each stage in the bespoke fitting process."
    )
    results: Optional[BespokeOptimizationResults] = Field(
        None,
        description="The final result of the bespoke optimization if the full workflow "
        "is finished, or ``None`` otherwise.",
    )

    @property
    def bespoke_force_field(self) -> Optional[ForceField]:
        """The final bespoke force field if the bespoke fitting workflow is complete."""

        if self.results is None or self.results.refit_force_field is None:
            return None

        return ForceField(
            self.results.refit_force_field, allow_cosmetic_attributes=True
        )

    @property
    def status(self) -> Status:

        pending_stages = [stage for stage in self.stages if stage.status == "waiting"]

        running_stages = [stage for stage in self.stages if stage.status == "running"]
        assert len(running_stages) < 2

        running_stage = None if len(running_stages) == 0 else running_stages[0]

        complete_stages = [
            stage
            for stage in self.stages
            if stage not in pending_stages and stage not in running_stages
        ]

        if (
            running_stage is None
            and len(complete_stages) == 0
            and len(pending_stages) > 0
        ):
            return "waiting"

        if any(stage.status == "errored" for stage in complete_stages):
            return "errored"

        if running_stage is not None or len(pending_stages) > 0:
            return "running"

        if all(stage.status == "success" for stage in complete_stages):
            return "success"

        raise NotImplementedError()

    @property
    def error(self) -> Optional[str]:
        """The error that caused the fitting to fail if any"""

        if self.status != "errored":
            return None

        message = next(
            iter(stage.error for stage in self.stages if stage.status == "errored")
        )
        return "unknown error" if message is None else message

    @classmethod
    def from_response(cls: Type[_T], response: CoordinatorGETResponse) -> _T:
        """Creates an instance of this object from the response from a bespoke
        coordinator service."""

        return cls(
            smiles=response.smiles,
            stages=[
                BespokeExecutorStageOutput(
                    type=stage.type, status=stage.status, error=stage.error
                )
                for stage in response.stages
            ],
            results=response.results,
        )


class BespokeExecutor:
    """The main class for generating a bespoke set of parameters for molecules based on
    bespoke optimization schemas.
    """

    def __init__(
        self,
        n_fragmenter_workers: int = 1,
        fragmenter_worker_config: BespokeWorkerConfig = BespokeWorkerConfig(),
        n_qc_compute_workers: int = 1,
        qc_compute_worker_config: BespokeWorkerConfig = BespokeWorkerConfig(),
        n_optimizer_workers: int = 1,
        optimizer_worker_config: BespokeWorkerConfig = BespokeWorkerConfig(),
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
        self._fragmenter_worker_config = fragmenter_worker_config
        self._n_qc_compute_workers = n_qc_compute_workers
        self._qc_compute_worker_config = qc_compute_worker_config
        self._n_optimizer_workers = n_optimizer_workers
        self._optimizer_worker_config = optimizer_worker_config

        self._directory = directory
        self._remove_directory = directory is None

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

        with Settings(
            BEFLOW_FRAGMENTER_WORKER_N_CORES=self._fragmenter_worker_config.n_cores,
            BEFLOW_FRAGMENTER_WORKER_MAX_MEM=self._fragmenter_worker_config.max_memory,
            BEFLOW_QC_COMPUTE_WORKER_N_CORES=self._qc_compute_worker_config.n_cores,
            BEFLOW_QC_COMPUTE_WORKER_MAX_MEM=self._qc_compute_worker_config.max_memory,
            BEFLOW_OPTIMIZER_WORKER_N_CORES=self._optimizer_worker_config.n_cores,
            BEFLOW_OPTIMIZER_WORKER_MAX_MEM=self._optimizer_worker_config.max_memory,
        ).apply_env():

            for worker_settings, n_workers, config in (
                (
                    settings.fragmenter_settings,
                    self._n_fragmenter_workers,
                    self._fragmenter_worker_config,
                ),
                (
                    settings.qc_compute_settings,
                    self._n_qc_compute_workers,
                    self._qc_compute_worker_config,
                ),
                (
                    settings.optimizer_settings,
                    self._n_optimizer_workers,
                    self._optimizer_worker_config,
                ),
            ):

                if n_workers == 0:
                    continue

                worker_module = importlib.import_module(worker_settings.import_path)
                importlib.reload(worker_module)  # Ensure settings are reloaded

                worker_app = getattr(worker_module, "celery_app")

                assert isinstance(
                    worker_app, celery.Celery
                ), "workers must be celery based"

                self._worker_processes.append(
                    spawn_worker(worker_app, concurrency=n_workers)
                )

    def _start(self, asynchronous=False):
        """Launch the executor, allowing it to receive and run bespoke optimizations.

        Args:
            asynchronous: Whether to run the executor asynchronously.
        """

        if self._started:
            raise RuntimeError("This executor is already running.")

        self._started = True

        if self._directory is None:
            self._directory = mkdtemp()
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

    def _stop(self):
        """Stop the executor from running and clean ip any associated processes."""

        if not self._started:
            raise RuntimeError("The executor is not running.")

        self._started = False
        self._cleanup_processes()

        atexit.unregister(self._cleanup_processes)

        if self._remove_directory:
            shutil.rmtree(self._directory, ignore_errors=True)

    @staticmethod
    def submit(input_schema: BespokeOptimizationSchema) -> str:
        """Submits a new bespoke fitting workflow to the executor.

        Args:
            input_schema: The schema defining the optimization to perform.

        Returns:
            The unique ID assigned to the optimization to perform.
        """
        request = requests.post(
            _coordinator_endpoint(),
            data=CoordinatorPOSTBody(input_schema=input_schema).json(),
        )
        request.raise_for_status()

        return CoordinatorPOSTResponse.parse_raw(request.text).id

    @staticmethod
    def retrieve(optimization_id: str) -> BespokeExecutorOutput:
        """Retrieve the current state of a running bespoke fitting workflow.

        Args:
            optimization_id: The unique ID associated with the running optimization.
        """

        optimization_href = f"{_coordinator_endpoint()}/{optimization_id}"

        return BespokeExecutorOutput.from_response(
            _query_coordinator(optimization_href)
        )

    def __enter__(self):
        self._start(asynchronous=True)
        return self

    def __exit__(self, *args):
        self._stop()


def _query_coordinator(optimization_href: str) -> CoordinatorGETResponse:

    coordinator_request = requests.get(optimization_href)
    coordinator_request.raise_for_status()

    response = CoordinatorGETResponse.parse_raw(coordinator_request.text)
    return response


def _wait_for_stage(
    optimization_href: str, stage_type: str, frequency: Union[int, float] = 5
) -> CoordinatorGETStageStatus:

    while True:

        response = _query_coordinator(optimization_href)

        stage = {stage.type: stage for stage in response.stages}[stage_type]

        if stage.status in ["errored", "success"]:
            break

        time.sleep(frequency)

    return stage


def wait_until_complete(
    optimization_id: str,
    console: Optional["rich.Console"] = None,
    frequency: Union[int, float] = 5,
) -> BespokeExecutorOutput:
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

    initial_response = _query_coordinator(optimization_href)
    stage_types = [stage.type for stage in initial_response.stages]

    stage_messages = {
        "fragmentation": "fragmenting the molecule",
        "qc-generation": "generating bespoke QC data",
        "optimization": "optimizing the parameters",
    }

    for stage_type in stage_messages:

        if stage_type not in stage_types:
            continue

        with console.status(stage_messages[stage_type]):
            stage = _wait_for_stage(optimization_href, stage_type, frequency)

        if stage.status == "errored":

            console.print(f"[[red]x[/red]] {stage_type} failed")
            console.print(Padding(stage.error, (1, 0, 0, 1)))

            break

        console.print(f"[[green]✓[/green]] {stage_type} successful")

    final_response = _query_coordinator(optimization_href)
    return BespokeExecutorOutput.from_response(final_response)
