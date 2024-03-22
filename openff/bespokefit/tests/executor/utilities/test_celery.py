import functools

import celery
import pytest
from celery import shared_task

from openff.bespokefit.executor.utilities.celery import (
    _spawn_worker,
    configure_celery_app,
    get_status,
    get_task_information,
    spawn_worker,
)
from openff.bespokefit.tests.executor.mocking.celery import mock_celery_result


@shared_task
def mock_task_success():
    return '{"key": "value"}'


@shared_task
def mock_task_error():
    raise RuntimeError("mock error occured")


@pytest.mark.parametrize(
    "task_result, expected_status",
    [
        (mock_celery_result(status="PENDING"), "waiting"),
        (mock_celery_result(status="STARTED"), "running"),
        (mock_celery_result(status="RETRY"), "running"),
        (mock_celery_result(status="FAILURE"), "errored"),
        (mock_celery_result(status="SUCCESS"), "success"),
    ],
)
def test_get_status(task_result, expected_status):
    assert get_status(task_result) == expected_status


def test_configure_celery_app(redis_connection):
    celery_app = configure_celery_app(
        app_name="test-app-name",
        redis_connection=redis_connection,
        include=["openff.bespokefit.executor.services.fragmenter.worker"],
    )

    assert isinstance(celery_app, celery.Celery)

    assert celery_app.main == "test-app-name"

    assert celery_app.conf.task_track_started is True
    assert celery_app.conf.task_default_queue == "test-app-name"

    assert (
        celery_app.backend.client.connection_pool.connection_kwargs["port"]
        == redis_connection.connection_pool.connection_kwargs["port"]
    )


def test_spawn_no_worker(celery_app):
    assert spawn_worker(celery_app, concurrency=0) is None


@pytest.mark.parametrize(
    "spawn_function",
    [_spawn_worker, functools.partial(spawn_worker, asynchronous=False)],
)
def test_spawn_worker(spawn_function, celery_app, monkeypatch):
    started = False

    def mock_start(self):
        nonlocal started
        started = True

    monkeypatch.setattr(celery_app.Worker, "start", mock_start)

    spawn_function(celery_app, concurrency=1)
    assert started


def test_get_task_information_success(celery_app, celery_worker):
    task_result = mock_task_success.delay()
    task_result.get(timeout=10)

    task_info = get_task_information(celery_app, task_result.id)

    assert task_info["id"] == task_result.id
    assert task_info["status"] == "success"
    assert task_info["error"] is None
    assert task_info["result"] == {"key": "value"}


def test_get_task_information_error(celery_app, celery_worker):
    task_result = mock_task_error.delay()
    task_result.get(propagate=False, timeout=10)

    task_info = get_task_information(celery_app, task_result.id)

    assert task_info["id"] == task_result.id
    assert task_info["status"] == "errored"
    assert task_info["result"] is None

    assert task_info["error"]["type"] == "RuntimeError"
    assert task_info["error"]["message"] == "mock error occured"
    assert task_info["error"]["traceback"] is not None
