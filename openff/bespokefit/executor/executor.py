import functools
import importlib
import logging
import multiprocessing
import os
import time
from typing import Optional, Union

import celery
import requests
from openff.utilities import temporary_cd

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETResponse,
    CoordinatorPOSTBody,
    CoordinatorPOSTResponse,
)
from openff.bespokefit.executor.services.gateway import launch as launch_gateway
from openff.bespokefit.executor.services.gateway import wait_for_gateway
from openff.bespokefit.executor.utilities.celery import spawn_worker
from openff.bespokefit.executor.utilities.redis import is_redis_available, launch_redis
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema

_logger = logging.getLogger(__name__)


class BespokeExecutor:
    """The main class for generating a bespoke set of parameters for molecules based on
    bespoke optimization schemas.
    """

    def __init__(
        self,
        n_fragmenter_workers: int = 0,
        n_qc_compute_workers: int = 0,
        n_optimizer_workers: int = 0,
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

    def _launch_redis(self):
        """Launches a redis server if an existing one cannot be found."""

        if self._launch_redis_if_unavailable and not is_redis_available(
            host=settings.BEFLOW_REDIS_ADDRESS, port=settings.BEFLOW_REDIS_PORT
        ):

            redis_log_file = open("redis.log", "w")
            launch_redis(settings.BEFLOW_REDIS_PORT, redis_log_file, redis_log_file)

    def _launch_workers(self):
        """Launches any service workers if requested."""

        for import_path, n_workers in {
            (settings.BEFLOW_FRAGMENTER_WORKER, self._n_fragmenter_workers),
            (settings.BEFLOW_QC_COMPUTE_WORKER, self._n_qc_compute_workers),
            (settings.BEFLOW_OPTIMIZER_WORKER, self._n_optimizer_workers),
        }:

            worker_module = importlib.import_module(import_path)
            worker_app = getattr(worker_module, "celery_app")

            assert isinstance(worker_app, celery.Celery), "workers must be celery based"
            spawn_worker(worker_app, concurrency=n_workers)

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

        if self._gateway_process is not None and self._gateway_process.is_alive():

            self._gateway_process.terminate()
            self._gateway_process.join()

    def submit(self, input_schema: BespokeOptimizationSchema) -> str:

        if not self._started:
            raise RuntimeError("The executor is not running.")

        request = requests.post(
            (
                f"http://127.0.0.1:"
                f"{settings.BEFLOW_GATEWAY_PORT}"
                f"{settings.BEFLOW_API_V1_STR}/"
                f"{settings.BEFLOW_COORDINATOR_PREFIX}"
            ),
            data=CoordinatorPOSTBody(input_schema=input_schema).json(),
        )
        request.raise_for_status()

        return CoordinatorPOSTResponse.parse_raw(request.text).optimization_id

    def wait_until_complete(
        self, optimization_id: str, frequency: Union[float, int] = 10
    ) -> CoordinatorGETResponse:
        """Wait for a specified optimization to complete and return the results.

        Args:
            optimization_id: The unique id of the optimization to wait for.
            frequency: The frequency (seconds) with which to check if the optimization
                has completed.

        Returns:
            The output of running the optimization.
        """

        if not self._started:
            raise RuntimeError("The executor is not running.")

        while True:

            try:

                request = requests.get(
                    (
                        f"http://127.0.0.1:"
                        f"{settings.BEFLOW_GATEWAY_PORT}"
                        f"{settings.BEFLOW_API_V1_STR}/"
                        f"{settings.BEFLOW_COORDINATOR_PREFIX}/"
                        f"{optimization_id}"
                    )
                )
                request.raise_for_status()

                response = CoordinatorGETResponse.parse_raw(request.text)

                if all(
                    stage.stage_status == "success" for stage in response.stages
                ) or any(stage.stage_status == "errored" for stage in response.stages):

                    return response

                time.sleep(frequency)

            except KeyboardInterrupt:
                break

    def __enter__(self):
        self.start(asynchronous=True)
        return self

    def __exit__(self, *args):
        self.stop()
