import importlib
import os.path

import pytest
import requests_mock

from openff.bespokefit.executor.executor import BespokeExecutor
from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETResponse,
    CoordinatorGETStageStatus,
    CoordinatorPOSTResponse,
)


def test_init():

    n_fragmenter_workers = 1
    n_qc_compute_workers = 2
    n_optimizer_workers = 3
    directory = "mock-directory"
    launch_redis_if_unavailable = False

    executor = BespokeExecutor(
        n_fragmenter_workers,
        n_qc_compute_workers,
        n_optimizer_workers,
        directory,
        launch_redis_if_unavailable,
    )

    assert executor._n_fragmenter_workers == n_fragmenter_workers
    assert executor._n_qc_compute_workers == n_qc_compute_workers
    assert executor._n_optimizer_workers == n_optimizer_workers

    assert executor._directory == directory
    assert executor._launch_redis_if_unavailable == launch_redis_if_unavailable


@pytest.mark.parametrize("launch_redis_if_unavailable", [False, True])
def test_launch_redis(monkeypatch, launch_redis_if_unavailable):

    redis_launched = False

    def mock_launch_redis(*_, **__):
        nonlocal redis_launched
        redis_launched = True

    executor_module = importlib.import_module("openff.bespokefit.executor.executor")
    monkeypatch.setattr(executor_module, "launch_redis", mock_launch_redis)

    executor = BespokeExecutor(
        directory=None, launch_redis_if_unavailable=launch_redis_if_unavailable
    )
    executor._launch_redis()

    assert redis_launched == launch_redis_if_unavailable


def test_launch_workers(monkeypatch):

    launched_workers = {}

    def mock_spawn_worker(app, concurrency):
        launched_workers[app.main] = concurrency

    executor_module = importlib.import_module("openff.bespokefit.executor.executor")
    monkeypatch.setattr(executor_module, "spawn_worker", mock_spawn_worker)

    executor = BespokeExecutor(
        n_fragmenter_workers=3,
        n_qc_compute_workers=2,
        n_optimizer_workers=1,
        directory=None,
        launch_redis_if_unavailable=False,
    )
    executor._launch_workers()

    assert launched_workers == {"fragmenter": 3, "qcgenerator": 2, "optimizer": 1}


def test_start_already_started():

    executor = BespokeExecutor()
    executor._started = True

    with pytest.raises(RuntimeError, match="This executor is already running."):
        executor.start()


def test_start_stop(tmpdir):

    executor = BespokeExecutor(
        n_fragmenter_workers=0,
        n_qc_compute_workers=0,
        n_optimizer_workers=0,
        directory=os.path.join(tmpdir, "mock-exe-dir"),
        launch_redis_if_unavailable=False,
    )
    executor.start(asynchronous=True)
    assert executor._started is True
    assert executor._gateway_process.is_alive()

    dir_found = os.path.isdir(os.path.join(tmpdir, "mock-exe-dir"))

    executor.stop()
    assert executor._started is False
    assert not executor._gateway_process.is_alive()

    assert dir_found


def test_stop_not_started():

    executor = BespokeExecutor()

    with pytest.raises(RuntimeError, match="The executor is not running."):
        executor.stop()


def test_submit(bespoke_optimization_schema):

    expected = CoordinatorPOSTResponse(id="mock-id", href="")

    with requests_mock.Mocker() as m:

        m.post(
            (
                f"http://127.0.0.1:"
                f"{settings.BEFLOW_GATEWAY_PORT}"
                f"{settings.BEFLOW_API_V1_STR}/"
                f"{settings.BEFLOW_COORDINATOR_PREFIX}"
            ),
            text=expected.json(),
        )

        executor = BespokeExecutor()
        executor._started = True

        result = executor.submit(bespoke_optimization_schema)
        assert result == expected.id


def test_submit_not_started(bespoke_optimization_schema):

    executor = BespokeExecutor()

    with pytest.raises(RuntimeError, match="The executor is not running."):
        executor.submit(bespoke_optimization_schema)


@pytest.mark.parametrize("expected_stage_status", ["success", "errored"])
def test_wait_until_complete(expected_stage_status):

    mock_response = CoordinatorGETResponse(
        id="mock-id",
        href="",
        stages=[
            CoordinatorGETStageStatus(
                type="fragmentation",
                status="running",
                error=None,
                results=None,
            )
        ],
    )

    def mock_callback(request, context):
        context.status_code = 200

        return_value = mock_response.json()
        mock_response.stages[0].status = expected_stage_status

        return return_value

    with requests_mock.Mocker() as m:

        m.get(
            (
                f"http://127.0.0.1:"
                f"{settings.BEFLOW_GATEWAY_PORT}"
                f"{settings.BEFLOW_API_V1_STR}/"
                f"{settings.BEFLOW_COORDINATOR_PREFIX}/"
                f"{mock_response.id}"
            ),
            text=mock_callback,
        )

        executor = BespokeExecutor()
        executor._started = True

        response = executor.wait_until_complete(mock_response.id, frequency=0.1)

        assert isinstance(response, CoordinatorGETResponse)
        assert response.stages[0].status == expected_stage_status


def test_wait_until_complete_not_started(bespoke_optimization_schema):

    executor = BespokeExecutor()

    with pytest.raises(RuntimeError, match="The executor is not running."):
        executor.wait_until_complete("mock-id")


def test_enter_exit(tmpdir):

    executor = BespokeExecutor(
        n_fragmenter_workers=0,
        n_qc_compute_workers=0,
        n_optimizer_workers=0,
        directory=os.path.join(tmpdir, "mock-exe-dir"),
        launch_redis_if_unavailable=False,
    )

    with executor:

        assert executor._started is True
        assert executor._gateway_process.is_alive()

        dir_found = os.path.isdir(os.path.join(tmpdir, "mock-exe-dir"))

    assert executor._started is False
    assert not executor._gateway_process.is_alive()

    assert dir_found
