import importlib
import os.path
from contextlib import contextmanager

import pytest
import requests_mock
from rich import get_console

from openff.bespokefit.executor import BespokeExecutor, wait_until_complete
from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETResponse,
    CoordinatorGETStageStatus,
    CoordinatorPOSTResponse,
)


@contextmanager
def mock_get_response(stage_status="running") -> CoordinatorGETResponse:

    mock_id = "mock-id"

    mock_href = (
        f"http://127.0.0.1:"
        f"{settings.BEFLOW_GATEWAY_PORT}"
        f"{settings.BEFLOW_API_V1_STR}/"
        f"{settings.BEFLOW_COORDINATOR_PREFIX}/"
        f"{mock_id}"
    )
    mock_response = CoordinatorGETResponse(
        id=mock_id,
        self=mock_href,
        stages=[
            CoordinatorGETStageStatus(
                type="fragmentation", status=stage_status, error=None, results=None
            )
        ],
    )

    with requests_mock.Mocker() as m:

        m.get(mock_href, text=mock_response.json())
        yield mock_response


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

    expected = CoordinatorPOSTResponse(id="mock-id", self="")

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
        assert result.id == expected.id


def test_submit_not_started(bespoke_optimization_schema):

    executor = BespokeExecutor()

    with pytest.raises(RuntimeError, match="The executor is not running."):
        executor.submit(bespoke_optimization_schema)


@pytest.mark.parametrize("status_code", [200, 404])
def test_query_coordinator(status_code: int):

    from openff.bespokefit.executor.executor import _query_coordinator

    mock_response = CoordinatorGETResponse(
        id="mock-id",
        self="",
        stages=[
            CoordinatorGETStageStatus(
                type="fragmentation", status="running", error=None, results=None
            )
        ],
    )

    def mock_callback(request, context):
        context.status_code = status_code
        return mock_response.json()

    mock_href = (
        f"http://127.0.0.1:"
        f"{settings.BEFLOW_GATEWAY_PORT}"
        f"{settings.BEFLOW_API_V1_STR}/"
        f"{settings.BEFLOW_COORDINATOR_PREFIX}/"
        f"{mock_response.id}"
    )

    with requests_mock.Mocker() as m:

        m.get(mock_href, text=mock_callback)
        response, error = _query_coordinator(mock_href)

    assert (response is None) == (status_code == 404)
    assert (error is None) == (status_code == 200)

    if status_code == 404:
        assert "404" in str(error)
    else:
        assert response.json() == mock_response.json()


@pytest.mark.parametrize("status", ["success", "errored"])
def test_wait_for_stage(status):

    from openff.bespokefit.executor.executor import _wait_for_stage

    mock_response = CoordinatorGETResponse(
        id="mock-id",
        self="",
        stages=[
            CoordinatorGETStageStatus(
                type="fragmentation", status="running", error=None, results=None
            )
        ],
    )

    n_requests = 0

    def mock_callback(request, context):
        context.status_code = 200

        response_json = mock_response.json()
        mock_response.stages[0].status = status

        nonlocal n_requests
        n_requests += 1

        return response_json

    mock_href = (
        f"http://127.0.0.1:"
        f"{settings.BEFLOW_GATEWAY_PORT}"
        f"{settings.BEFLOW_API_V1_STR}/"
        f"{settings.BEFLOW_COORDINATOR_PREFIX}/"
        f"{mock_response.id}"
    )

    with requests_mock.Mocker() as m:

        m.get(mock_href, text=mock_callback)

        response, error = _wait_for_stage(mock_href, "fragmentation", frequency=0.01)

    assert error is None
    assert response is not None

    assert n_requests == 2

    assert response.status == status
    assert response.error is None
    assert response.type == "fragmentation"
    assert response.results is None


def test_wait_for_error():

    from openff.bespokefit.executor.executor import _wait_for_stage

    mock_href = (
        f"http://127.0.0.1:"
        f"{settings.BEFLOW_GATEWAY_PORT}"
        f"{settings.BEFLOW_API_V1_STR}/"
        f"{settings.BEFLOW_COORDINATOR_PREFIX}/1"
    )

    with requests_mock.Mocker() as m:

        m.get(mock_href, text="missing", status_code=404)

        response, error = _wait_for_stage(mock_href, "fragmentation", frequency=0.01)

    assert error is not None
    assert response is None

    assert "404" in str(error)


def test_wait_until_complete_initial_error():

    mock_href = (
        f"http://127.0.0.1:"
        f"{settings.BEFLOW_GATEWAY_PORT}"
        f"{settings.BEFLOW_API_V1_STR}/"
        f"{settings.BEFLOW_COORDINATOR_PREFIX}/1"
    )

    with requests_mock.Mocker() as m:

        m.get(mock_href, text="missing", status_code=404)

        # Make sure we're resilient to missing requests / the server being doing.
        with get_console().capture() as capture:
            response = wait_until_complete("1")

    assert response is None
    assert "404" in capture.get()


def test_wait_until_complete_final_error(monkeypatch):

    from openff.bespokefit.executor import executor as executor_module

    mock_response = CoordinatorGETResponse(
        id="mock-id",
        self="",
        stages=[
            CoordinatorGETStageStatus(
                type="fragmentation", status="running", error=None, results=None
            )
        ],
    )
    n_mock_requests = 0

    def mock_query_coordinator(*_):

        nonlocal n_mock_requests
        n_mock_requests += 1

        return (
            (mock_response, None)
            if n_mock_requests == 1
            else (None, RuntimeError("mock-error"))
        )

    monkeypatch.setattr(
        executor_module,
        "_wait_for_stage",
        lambda *_: (
            CoordinatorGETStageStatus(
                type="fragmentation", error=None, results=None, status="success"
            ),
            None,
        ),
    )
    monkeypatch.setattr(executor_module, "_query_coordinator", mock_query_coordinator)

    with get_console().capture() as capture:
        response = wait_until_complete("1")

    assert n_mock_requests == 2
    assert response is None
    assert "fragmentation successful" in capture.get()
    assert "mock-error" in capture.get()


@pytest.mark.parametrize("stage_error", [None, RuntimeError("mock-error")])
def test_wait_until_complete_stage_uncaught_error(stage_error, monkeypatch):

    from openff.bespokefit.executor import executor as executor_module

    monkeypatch.setattr(
        executor_module, "_wait_for_stage", lambda *_: (None, stage_error)
    )

    with mock_get_response() as mock_response:

        with get_console().capture() as capture:
            response = wait_until_complete(mock_response.id)

    assert response is None

    if stage_error is None:
        assert response is None
    else:
        assert "mock-error" in capture.get()


def test_wait_until_complete_stage_error(monkeypatch):

    from openff.bespokefit.executor import executor as executor_module

    monkeypatch.setattr(
        executor_module,
        "_wait_for_stage",
        lambda *_: (
            CoordinatorGETStageStatus(
                type="fragmentation", error="mock-error", results=None, status="errored"
            ),
            None,
        ),
    )

    with mock_get_response() as mock_response:

        with get_console().capture() as capture:
            response = wait_until_complete(mock_response.id)

    assert "fragmentation failed" in capture.get()

    assert response is not None
    # Because we're just mocking a GET response we can't check on the stage status here
    assert isinstance(response, CoordinatorGETResponse)


def test_wait_until_complete():

    with mock_get_response("success") as mock_response:
        response = wait_until_complete(mock_response.id, frequency=0.1)

    assert isinstance(response, CoordinatorGETResponse)
    assert response.stages[0].status == "success"


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
