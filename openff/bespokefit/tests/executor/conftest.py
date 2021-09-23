import subprocess

import pytest
import redis

from openff.bespokefit.executor.utilities.redis import launch_redis


@pytest.fixture(scope="session")
def redis_session(tmpdir_factory):

    redis_exists_error = RuntimeError(
        "It looks like a redis server is already running with the test "
        "settings. Exiting early in-case this is a production redis server."
    )

    try:

        connection = redis.Redis(port=5678, db=0)

        keys = connection.keys("*")
        assert len(keys) == 0

    except redis.ConnectionError:
        pass
    except AssertionError:
        raise redis_exists_error
    else:
        raise redis_exists_error

    launch_redis(
        port=5678,
        stderr_file=subprocess.DEVNULL,
        stdout_file=subprocess.DEVNULL,
        persistent=False,
        directory=str(tmpdir_factory.mktemp("redis")),
    )


@pytest.fixture(scope="session")
def redis_connection(redis_session) -> redis.Redis:
    return redis.Redis(port=5678, db=0)


@pytest.fixture(scope="function", autouse=True)
def reset_redis(redis_connection, monkeypatch):

    redis_connection.flushdb()
