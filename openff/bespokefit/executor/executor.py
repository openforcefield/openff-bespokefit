import atexit
import functools
import importlib
import logging
import multiprocessing
import os
import shutil
import subprocess
from tempfile import mkdtemp
from typing import TYPE_CHECKING, List, Optional, Union

import celery
from typing_extensions import Literal

from openff.bespokefit._pydantic import BaseModel, Field
from openff.bespokefit.executor.services import Settings, current_settings
from openff.bespokefit.executor.services.gateway import launch as launch_gateway
from openff.bespokefit.executor.services.gateway import wait_for_gateway
from openff.bespokefit.executor.utilities.celery import spawn_worker
from openff.bespokefit.executor.utilities.redis import is_redis_available, launch_redis
from openff.bespokefit.utilities.tempcd import temporary_cd

if TYPE_CHECKING:
    import rich

    from openff.bespokefit.executor.client import BespokeExecutorOutput
    from openff.bespokefit.schema.fitting import BespokeOptimizationSchema

_logger = logging.getLogger(__name__)


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
        settings = current_settings()
        self._remove_directory = directory is None and not (
            settings.BEFLOW_OPTIMIZER_KEEP_FILES or settings.BEFLOW_KEEP_TMP_FILES
        )

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

        settings = current_settings()

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
            settings = current_settings()

            for worker_settings, n_workers in (
                (settings.fragmenter_settings, self._n_fragmenter_workers),
                (settings.qc_compute_settings, self._n_qc_compute_workers),
                (settings.optimizer_settings, self._n_optimizer_workers),
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

    def __enter__(self):
        self._start(asynchronous=True)
        return self

    def __exit__(self, *args):
        self._stop()

    @staticmethod
    def submit(input_schema: "BespokeOptimizationSchema") -> str:
        """Submits a new bespoke fitting workflow to the executor.

        Args:
            input_schema: The schema defining the optimization to perform.

        Returns:
            The unique ID assigned to the optimization to perform.
        """
        from openff.bespokefit.executor.client import BespokeFitClient
        from openff.bespokefit.executor.services import current_settings

        client = BespokeFitClient(settings=current_settings())

        return client.submit_optimization(input_schema=input_schema)

    @staticmethod
    def retrieve(optimization_id: str) -> "BespokeExecutorOutput":
        """Retrieve the current state of a running bespoke fitting workflow.

        Args:
            optimization_id: The unique ID associated with the running optimization.
        """

        from openff.bespokefit.executor.client import BespokeFitClient
        from openff.bespokefit.executor.services import current_settings

        client = BespokeFitClient(settings=current_settings())

        return client.get_optimization(optimization_id=optimization_id)


def wait_until_complete(
    optimization_id: str,
    console: Optional["rich.Console"] = None,
    frequency: Union[int, float] = 5,
) -> "BespokeExecutorOutput":
    """Wait for a specified optimization to complete and return the results.

    Args:
        optimization_id: The unique id of the optimization to wait for.
        console: The console to print to.
        frequency: The frequency (seconds) with which to poll the status of the
            optimization.

    Returns:
        The output of running the optimization.
    """
    from openff.bespokefit.executor.client import BespokeFitClient
    from openff.bespokefit.executor.services import current_settings

    client = BespokeFitClient(settings=current_settings())

    return client.wait_until_complete(
        optimization_id=optimization_id, console=console, frequency=frequency
    )
