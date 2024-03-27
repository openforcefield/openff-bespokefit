"""Utilities for interacting with Celery within the executor."""

import json
import multiprocessing
from typing import Any

from celery import Celery
from celery.result import AsyncResult
from redis import Redis
from typing_extensions import TypedDict

from openff.bespokefit.executor.services.models import Error
from openff.bespokefit.executor.utilities.typing import Status
from openff.bespokefit.utilities import current_settings


class TaskInformation(TypedDict):
    """Information about a task."""

    id: str

    status: Status

    result: dict[str, Any] | None
    error: dict[str, Any] | None


def get_status(task_result: AsyncResult) -> Status:
    """Get the status of a task."""
    return {
        "PENDING": "waiting",
        "STARTED": "running",
        "RETRY": "running",
        "FAILURE": "errored",
        "SUCCESS": "success",
    }[task_result.status]


def configure_celery_app(
    app_name: str,
    redis_connection: Redis,
    include: list[str] = None,
):
    """Configure this celery app."""
    settings = current_settings()
    redis_host_name = redis_connection.connection_pool.connection_kwargs["host"]
    redis_port = redis_connection.connection_pool.connection_kwargs["port"]
    redis_db = redis_connection.connection_pool.connection_kwargs["db"]
    password = settings.BEFLOW_REDIS_PASSWORD

    celery_app = Celery(
        app_name,
        backend=f"redis://:{password}@{redis_host_name}:{redis_port}/{redis_db}",
        broker=f"redis://:{password}@{redis_host_name}:{redis_port}/{redis_db}",
        include=include,
    )

    celery_app.conf.task_track_started = True
    celery_app.conf.task_default_queue = app_name
    celery_app.conf.broker_transport_options = {"visibility_timeout": 1000000}
    celery_app.conf.result_expires = None

    return celery_app


def _spawn_worker(celery_app, concurrency: int = 1, **kwargs):
    worker = celery_app.Worker(
        concurrency=concurrency,
        loglevel="INFO",
        logfile=f"celery-{celery_app.main}.log",
        quiet=True,
        hostname=celery_app.main,
        **kwargs,
    )
    worker.start()


def spawn_worker(
    celery_app,
    concurrency: int = 1,
    asynchronous: bool = True,
    **kwargs,
) -> multiprocessing.Process | None:
    """Spawn a worker."""
    if concurrency < 1:
        return

    if asynchronous:  # pragma: no cover
        worker_process = multiprocessing.Process(
            target=_spawn_worker,
            args=(celery_app, concurrency),
            daemon=True,
        )
        worker_process.start()

        return worker_process

    else:
        _spawn_worker(celery_app, concurrency, **kwargs)


def get_task_information(app: Celery, task_id: str) -> TaskInformation:
    """Get information about this task."""
    task_result = AsyncResult(task_id, app=app)

    task_output = (
        None
        if not isinstance(task_result.result, str)
        else json.loads(task_result.result)
    )

    task_raw_error = (
        None
        if not isinstance(task_result.result, BaseException)
        else task_result.result
    )
    task_error = (
        None
        if task_raw_error is None
        else Error(
            type=task_raw_error.__class__.__name__,
            message=str(task_raw_error),
            traceback=task_result.traceback,
        )
    )

    task_status = get_status(task_result)

    return TaskInformation(
        id=task_id,
        status=task_status,
        result=task_output if task_status != "errored" else None,
        error=None if not task_error else task_error.dict(),
    )
