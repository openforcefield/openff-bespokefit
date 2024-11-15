import pytest

from openff.bespokefit.cli.worker import worker_cli
from openff.bespokefit.executor.utilities import celery


@pytest.mark.parametrize(
    "worker_type",
    [
        pytest.param("fragmenter", id="fragmenter"),
        pytest.param("qc-compute", id="qc-compute"),
        pytest.param("optimizer", id="optimizer"),
    ],
)
def test_launch_worker(worker_type, runner, monkeypatch):
    """Test launching a worker of the correct type, note we do not start the worker this is tested
    in test_celery/test_spawn_worker
    """

    launched_workers = {}

    def mock_spawn_worker(app, concurrency, asynchronous, pool=None):
        launched_workers[app.main] = concurrency

    monkeypatch.setattr(celery, "spawn_worker", mock_spawn_worker)

    output = runner.invoke(worker_cli, args=["--worker-type", worker_type])
    assert output.exit_code == 0
    assert worker_type in output.output
