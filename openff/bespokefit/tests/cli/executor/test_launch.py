import inspect
import time

import click.exceptions
import pytest
import rich

from openff.bespokefit.cli.executor.launch import launch_cli, validate_redis_connection
from openff.bespokefit.executor import BespokeExecutor
from openff.bespokefit.executor.utilities.redis import RedisNotConfiguredError
from openff.bespokefit.tests.executor import patch_settings


@pytest.fixture(scope="module", autouse=True)
def configure_redis(redis_connection):
    with patch_settings(redis_connection):
        yield


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
    monkeypatch.setattr(BespokeExecutor, "_start", mock_start)

    output = runner.invoke(
        launch_cli,
        args=[
            "--directory",
            "mock-directory",
            "--n-fragmenter-workers",
            1,
            "--n-qc-compute-workers",
            2,
            "--n-optimizer-workers",
            3,
            "--no-launch-redis",
        ],
    )
    print(output.output)
    assert output.exit_code == 0


def test_validate_redis_connection_exists(redis_connection):
    console = rich.get_console()

    with console.capture() as capture:
        with pytest.raises(click.exceptions.Exit):
            validate_redis_connection(console, allow_existing=False)

    assert "a redis server is already running" in capture.get()
    assert "continuing to run would likely cause" in capture.get()


def test_validate_redis_connection_config(redis_connection, monkeypatch):
    from openff.bespokefit.executor.utilities import redis

    def mock_connect_to_default_redis():
        raise RedisNotConfiguredError("not configured")

    monkeypatch.setattr(
        redis,
        "connect_to_default_redis",
        mock_connect_to_default_redis,
    )

    console = rich.get_console()

    with console.capture() as capture:
        with pytest.raises(click.exceptions.Exit):
            validate_redis_connection(console)

    assert "not configured" in capture.get()
