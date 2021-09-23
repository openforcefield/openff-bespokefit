import functools
import importlib
import logging
import multiprocessing
import os
import time
from typing import Optional

import celery
import requests
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
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

_logger = logging.getLogger(__name__)


class BespokeExecutor:
    def __init__(
        self,
        n_fragmenter_workers: int = 0,
        n_qc_compute_workers: int = 0,
        n_optimizer_workers: int = 0,
        directory: str = "bespoke-executor",
        launch_redis_if_unavailable: bool = True,
    ):

        self._n_fragmenter_workers = n_fragmenter_workers
        self._n_qc_compute_workers = n_qc_compute_workers
        self._n_optimizer_workers = n_optimizer_workers

        self._directory = directory

        self._launch_redis_if_unavailable = launch_redis_if_unavailable

        self._started = False

        self._gateway_process: Optional[multiprocessing.Process] = None

    def _launch_redis(self):

        if self._launch_redis_if_unavailable and not is_redis_available(
            host=settings.BEFLOW_REDIS_ADDRESS, port=settings.BEFLOW_REDIS_PORT
        ):

            redis_log_file = open("redis.log", "w")
            launch_redis(settings.BEFLOW_REDIS_PORT, redis_log_file, redis_log_file)

    def _launch_workers(self):

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
                target=functools.partial(launch_gateway, self._directory), daemon=True
            )
            self._gateway_process.start()

            wait_for_gateway()

        else:

            launch_gateway(self._directory)

    def stop(self):

        if not self._started:
            raise ValueError("The executor is not running.")

        self._started = False

        if self._gateway_process is not None and self._gateway_process.is_alive():

            self._gateway_process.terminate()
            self._gateway_process.join()

    def submit(self, input_schema: BespokeOptimizationSchema) -> str:

        assert self._started, "the executor is not running"

        request = requests.post(
            "http://127.0.0.1:8000/api/v1/optimization",
            data=CoordinatorPOSTBody(input_schema=input_schema).json(),
        )

        return CoordinatorPOSTResponse.parse_raw(request.text).optimization_id

    def wait_until_complete(
        self, optimization_id: str, frequency: int = 10
    ) -> CoordinatorGETResponse:

        while True:

            try:

                request = requests.get(
                    f"http://127.0.0.1:8000/api/v1/optimization/{optimization_id}"
                )
                request.raise_for_status()

                response = CoordinatorGETResponse.parse_raw(request.text)

                # TODO: Return the actual result
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
