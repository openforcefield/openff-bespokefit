import os.path
import shutil

import pytest
from redis import Redis

from openff.bespokefit.executor.utilities.redis import (
    expected_redis_config_version,
    is_redis_available,
    launch_redis,
)


def test_launch_redis(tmpdir, bespoke_settings):
    assert not is_redis_available(
        host="localhost", port=1234, password=bespoke_settings.BEFLOW_REDIS_PASSWORD
    )

    redis_process = launch_redis(port=1234, directory=str(tmpdir), persistent=True)

    try:
        assert is_redis_available(
            host="localhost", port=1234, password=bespoke_settings.BEFLOW_REDIS_PASSWORD
        )

        redis_connection = Redis(
            host="localhost", port=1234, password=bespoke_settings.BEFLOW_REDIS_PASSWORD
        )

        assert (
            int(redis_connection.get("openff-bespokefit:redis-version"))
            == expected_redis_config_version()
        )

        assert redis_connection.get("test-key") is None
        redis_connection.set("test-key", "set")
        assert redis_connection.get("test-key") is not None

    finally:
        redis_process.terminate()
        redis_process.wait()

    assert not is_redis_available(
        host="localhost", port=1234, password=bespoke_settings.BEFLOW_REDIS_PASSWORD
    )

    assert os.path.isfile(os.path.join(tmpdir, "redis.db"))


def test_launch_redis_already_exists(tmpdir, bespoke_settings):
    assert not is_redis_available(
        host="localhost", port=1234, password=bespoke_settings.BEFLOW_REDIS_PASSWORD
    )

    redis_process = launch_redis(port=1234, directory=str(tmpdir), persistent=True)
    assert is_redis_available(
        host="localhost", port=1234, password=bespoke_settings.BEFLOW_REDIS_PASSWORD
    )

    with pytest.raises(RuntimeError, match="here is already a server running"):
        launch_redis(port=1234, directory=str(tmpdir))

    redis_process.terminate()
    redis_process.wait()

    assert not is_redis_available(
        host="localhost", port=1234, password=bespoke_settings.BEFLOW_REDIS_PASSWORD
    )


@pytest.mark.parametrize("missing_command", ["redis-server", "redis-cli"])
def test_launch_redis_missing_command(tmpdir, monkeypatch, missing_command):
    monkeypatch.setattr(
        shutil, "which", lambda x: None if x == missing_command else "some/path"
    )

    redis_process = None

    with pytest.raises(RuntimeError, match=f"The `{missing_command}`"):
        redis_process = launch_redis(port=1234, directory=str(tmpdir))

    if redis_process is not None:
        redis_process.terminate()
        redis_process.wait()
