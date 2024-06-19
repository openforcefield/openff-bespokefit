import importlib
import os.path
from contextlib import contextmanager

import pytest
import requests_mock
from openff.toolkit.typing.engines.smirnoff import ForceField

from openff.bespokefit.executor import (
    BespokeExecutor,
    BespokeExecutorOutput,
    BespokeExecutorStageOutput,
    BespokeFitClient,
)
from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETResponse,
    CoordinatorGETStageStatus,
    CoordinatorPOSTResponse,
)


@contextmanager
def mock_get_response(stage_status="running") -> CoordinatorGETResponse:
    settings = current_settings()

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
        smiles="CC",
        stages=[
            CoordinatorGETStageStatus(
                type="fragmentation", status=stage_status, error=None, results=None
            )
        ],
    )

    with requests_mock.Mocker() as m:
        m.get(mock_href, text=mock_response.json(by_alias=True))
        yield mock_response


class TestBespokeExecutorOutput:
    @pytest.fixture
    def mock_output(self, bespoke_optimization_results):
        return BespokeExecutorOutput(
            smiles="CC",
            stages=[
                BespokeExecutorStageOutput(
                    type="fragmentation", status="success", error=None
                )
            ],
            results=bespoke_optimization_results,
        )

    def test_bespoke_force_field(self, bespoke_optimization_results):
        assert isinstance(
            BespokeExecutorOutput(
                smiles="CC",
                stages=[
                    BespokeExecutorStageOutput(
                        type="fragmentation", status="success", error=None
                    )
                ],
                results=bespoke_optimization_results,
            ).bespoke_force_field,
            ForceField,
        )
        assert (
            BespokeExecutorOutput(
                smiles="CC",
                stages=[
                    BespokeExecutorStageOutput(
                        type="fragmentation", status="success", error=None
                    )
                ],
                results=None,
            ).bespoke_force_field
            is None
        )

    @pytest.mark.parametrize(
        "stages, expected_status",
        [
            (
                [
                    BespokeExecutorStageOutput(
                        type="fragmentation", status="waiting", error=None
                    )
                ],
                "waiting",
            ),
            (
                [
                    BespokeExecutorStageOutput(
                        type="fragmentation", status="success", error=None
                    ),
                    BespokeExecutorStageOutput(
                        type="qc-generation", status="waiting", error=None
                    ),
                ],
                "running",
            ),
            (
                [
                    BespokeExecutorStageOutput(
                        type="fragmentation", status="success", error=None
                    ),
                    BespokeExecutorStageOutput(
                        type="qc-generation", status="running", error=None
                    ),
                ],
                "running",
            ),
            (
                [
                    BespokeExecutorStageOutput(
                        type="fragmentation", status="errored", error=None
                    ),
                    BespokeExecutorStageOutput(
                        type="qc-generation", status="waiting", error=None
                    ),
                ],
                "errored",
            ),
            (
                [
                    BespokeExecutorStageOutput(
                        type="fragmentation", status="success", error=None
                    )
                ],
                "success",
            ),
            ([], "success"),
        ],
    )
    def test_status(self, stages, expected_status):
        output = BespokeExecutorOutput(smiles="CC", stages=stages)
        assert output.status == expected_status

    def test_error(self):
        assert (
            BespokeExecutorOutput(
                smiles="CC",
                stages=[
                    BespokeExecutorStageOutput(
                        type="fragmentation", status="errored", error="general error"
                    )
                ],
                results=None,
            ).error
            == "general error"
        )

    def test_from_response(self):
        output = BespokeExecutorOutput.from_response(
            CoordinatorGETResponse(
                id="mock-id",
                self="",
                smiles="CC",
                stages=[
                    CoordinatorGETStageStatus(
                        type="fragmentation", status="running", error=None, results=None
                    )
                ],
            )
        )
        assert len(output.stages) == 1
        assert output.stages[0].type == "fragmentation"


class TestBespokeExecutor:
    def test_init(self):
        n_fragmenter_workers = 1
        n_qc_compute_workers = 2
        n_optimizer_workers = 3
        directory = "mock-directory"
        launch_redis_if_unavailable = False

        executor = BespokeExecutor(
            n_fragmenter_workers=n_fragmenter_workers,
            n_qc_compute_workers=n_qc_compute_workers,
            n_optimizer_workers=n_optimizer_workers,
            directory=directory,
            launch_redis_if_unavailable=launch_redis_if_unavailable,
        )

        assert executor._n_fragmenter_workers == n_fragmenter_workers
        assert executor._n_qc_compute_workers == n_qc_compute_workers
        assert executor._n_optimizer_workers == n_optimizer_workers

        assert executor._directory == directory
        assert executor._launch_redis_if_unavailable == launch_redis_if_unavailable

    @pytest.mark.parametrize("launch_redis_if_unavailable", [False, True])
    def test_launch_redis(self, monkeypatch, launch_redis_if_unavailable):
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

    def test_launch_workers(self, monkeypatch):
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

    def test_start_already_started(self):
        executor = BespokeExecutor()
        executor._started = True

        with pytest.raises(RuntimeError, match="This executor is already running."):
            executor._start()

    def test_start_stop(self, tmpdir):
        executor = BespokeExecutor(
            n_fragmenter_workers=0,
            n_qc_compute_workers=0,
            n_optimizer_workers=0,
            directory=os.path.join(tmpdir, "mock-exe-dir"),
            launch_redis_if_unavailable=False,
        )
        executor._start(asynchronous=True)
        assert executor._started is True
        assert executor._gateway_process.is_alive()

        gateway_pid = executor._gateway_process.pid

        dir_found = os.path.isdir(os.path.join(tmpdir, "mock-exe-dir"))

        executor._stop()
        assert executor._started is False

        with pytest.raises(OSError):
            os.kill(gateway_pid, 0)

        assert dir_found

    def test_stop_not_started(self):
        executor = BespokeExecutor()

        with pytest.raises(RuntimeError, match="The executor is not running."):
            executor._stop()

    def test_submit(self, bespoke_optimization_schema):
        settings = current_settings()
        client = BespokeFitClient(settings=settings)
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

            result_id = client.submit_optimization(bespoke_optimization_schema)
            assert result_id == expected.id

    def test_retrieve(self, bespoke_optimization_schema):
        with mock_get_response():
            client = BespokeFitClient(settings=current_settings())
            output = client.get_optimization("mock-id")
            assert output.status == "running"

    def test_enter_exit(self, tmpdir):
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
            gateway_pid = executor._gateway_process.pid

            dir_found = os.path.isdir(os.path.join(tmpdir, "mock-exe-dir"))

        assert executor._started is False

        with pytest.raises(OSError):
            os.kill(gateway_pid, 0)

        assert dir_found


def test_query_coordinator():

    mock_response = CoordinatorGETResponse(
        id="mock-id",
        self="",
        smiles="CC",
        stages=[
            CoordinatorGETStageStatus(
                type="fragmentation", status="running", error=None, results=None
            )
        ],
    )

    def mock_callback(request, context):
        context.status_code = 200
        return mock_response.json(by_alias=True)

    settings = current_settings()
    client = BespokeFitClient(settings=settings)

    mock_href = (
        f"http://127.0.0.1:"
        f"{settings.BEFLOW_GATEWAY_PORT}"
        f"{settings.BEFLOW_API_V1_STR}/"
        f"{settings.BEFLOW_COORDINATOR_PREFIX}/"
        f"{mock_response.id}"
    )

    with requests_mock.Mocker() as m:
        m.get(mock_href, text=mock_callback)
        response = client._query_coordinator(mock_href)

    assert response.json() == mock_response.json()


@pytest.mark.parametrize("status", ["success", "errored"])
def test_wait_for_stage(status):

    mock_response = CoordinatorGETResponse(
        id="mock-id",
        self="",
        smiles="CC",
        stages=[
            CoordinatorGETStageStatus(
                type="fragmentation", status="running", error=None, results=None
            )
        ],
    )

    n_requests = 0

    def mock_callback(request, context):
        context.status_code = 200

        response_json = mock_response.json(by_alias=True)
        mock_response.stages[0].status = status

        nonlocal n_requests
        n_requests += 1

        return response_json

    settings = current_settings()
    client = BespokeFitClient(settings=settings)

    mock_href = (
        f"http://127.0.0.1:"
        f"{settings.BEFLOW_GATEWAY_PORT}"
        f"{settings.BEFLOW_API_V1_STR}/"
        f"{settings.BEFLOW_COORDINATOR_PREFIX}/"
        f"{mock_response.id}"
    )

    with requests_mock.Mocker() as m:
        m.get(mock_href, text=mock_callback)

        response = client._wait_for_stage(
            mock_response.id, "fragmentation", frequency=0.01
        )

    assert response is not None
    assert n_requests == 2
    assert response.status == status
    assert response.error is None
    assert response.type == "fragmentation"
    assert response.results is None


def test_wait_until_complete():
    settings = current_settings()
    client = BespokeFitClient(settings=settings)
    with mock_get_response("success") as mock_response:
        response = client.wait_until_complete(mock_response.id, frequency=0.1)

    assert isinstance(response, BespokeExecutorOutput)
    assert response.stages[0].status == "success"
