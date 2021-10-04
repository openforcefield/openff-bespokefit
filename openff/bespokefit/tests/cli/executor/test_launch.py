import inspect
import time

from openff.bespokefit.cli.executor.launch import launch_cli
from openff.bespokefit.executor import BespokeExecutor


def test_launch(runner, monkeypatch):

    old_sleep = time.sleep

    def mock_sleep(*args, **kwargs):

        frame = inspect.stack()[1]
        file_name = inspect.getmodule(frame[0]).__file__

        if file_name.endswith("launch.py"):
            raise KeyboardInterrupt()

        old_sleep(*args, **kwargs)

    def mock_start(self, *args, **kwargs):

        assert self._n_fragmenter_workers == 1
        assert self._n_qc_compute_workers == 2
        assert self._n_optimizer_workers == 3

        assert self._directory == "mock-directory"

        assert self._launch_redis_if_unavailable is False

        self._started = True

    monkeypatch.setattr(time, "sleep", mock_sleep)
    monkeypatch.setattr(BespokeExecutor, "start", mock_start)

    output = runner.invoke(
        launch_cli,
        args=[
            "--directory",
            "mock-directory",
            "--n-fragmenter",
            1,
            "--n-qc-compute",
            2,
            "--n-optimizer",
            3,
            "--no-launch-redis",
        ],
    )
    print(output.output)
    assert output.exit_code == 0
