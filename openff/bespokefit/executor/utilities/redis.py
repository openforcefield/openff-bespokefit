"""Utilities for interacting with redis."""
import atexit
import functools
import os
import shlex
import shutil
import subprocess
import time
from typing import IO, Optional, Union

import redis

from openff.bespokefit.executor.services import current_settings

__REDIS_VERSION: int = 1
__CONNECTION_POOL: dict[
    tuple[str, int, Optional[int], Optional[str], bool], redis.Redis
] = {}


class RedisNotConfiguredError(BaseException):
    """
    An exception raised when connecting to a redis server that doesn't appear to have been configured by `openff-bespokefit`.
    """


class RedisBadConfigurationError(BaseException):
    """
    An exception raised when connecting to a redis server that doesn't appear to have been correctly configured for use with `openff-bespokefit`.
    """


def expected_redis_config_version() -> int:
    """Return the expected redis config version."""
    return __REDIS_VERSION


def connect_to_default_redis(validate: bool = True) -> redis.Redis:
    """
    Connect to a redis server using the settings defined by the `BEFLOW_REDIS_ADDRESS`, `BEFLOW_REDIS_PORT` and `BEFLOW_REDIS_PORT` settings.
    """
    settings = current_settings()

    return connect_to_redis(
        host=settings.BEFLOW_REDIS_ADDRESS,
        port=settings.BEFLOW_REDIS_PORT,
        db=settings.BEFLOW_REDIS_DB,
        password=settings.BEFLOW_REDIS_PASSWORD,
        validate=validate,
    )


def connect_to_redis(
    host: str, port: int, db: int, validate: bool = True, password: Optional[str] = None
) -> redis.Redis:
    """Connects to a redis server using the specified settings."""

    connection_key = (host, port, db, password, validate)

    if connection_key in __CONNECTION_POOL:
        return __CONNECTION_POOL[connection_key]

    connection = redis.Redis(host=host, port=port, db=db, password=password)

    if validate:
        version = connection.get("openff-bespokefit:redis-version")

        if version is None:
            raise RedisNotConfiguredError(
                f"The redis server at host={host} and port={port} does not contain a "
                f"`openff-bespokefit:redis-version` key. This likely means it was not "
                f"configured for use with OpenFF BespokeFit. Alternatively if you have "
                f"just updated to a new version of OpenFF BespokeFit, try deleting any "
                f"old `redis.db` files.",
            )

        elif int(version) != __REDIS_VERSION:
            raise RedisBadConfigurationError(
                f"The redis server at host={host} and port={port} expects a version of "
                f"OpenFF BespokeFit that supports a redis configurations with version "
                f"{version}, while the current version only supports version "
                f"{__REDIS_VERSION}.",
            )

    __CONNECTION_POOL[connection_key] = connection
    return connection


def is_redis_available(
    host: str, port: int = 6363, password: Optional[str] = None
) -> bool:
    """Returns whether a server running on the local host on a particular port is
    available.
    """

    redis_client = redis.Redis(host=host, port=port, password=password)

    try:
        redis_client.get("null")

    except (redis.exceptions.ConnectionError, redis.exceptions.BusyLoadingError):
        return False

    return True


def _cleanup_redis(redis_process: subprocess.Popen):
    redis_process.terminate()


def launch_redis(
    port: int = 6363,
    stderr_file: Optional[Union[IO, int]] = None,
    stdout_file: Optional[Union[IO, int]] = None,
    directory: Optional[str] = None,
    persistent: bool = True,
    terminate_at_exit: bool = True,
) -> subprocess.Popen:
    """Launch a redis server."""
    settings = current_settings()
    redis_server_path = shutil.which("redis-server")

    if redis_server_path is None:
        raise RuntimeError(
            "The `redis-server` command could not be found. Please make sure `redis` is "
            "correctly installed.",
        )

    redis_cli_path = shutil.which("redis-cli")

    if redis_cli_path is None:
        raise RuntimeError(
            "The `redis-cli` command could not be found. Please make sure `redis` is "
            "correctly installed.",
        )

    if is_redis_available(
        host="localhost", port=port, password=settings.BEFLOW_REDIS_PASSWORD
    ):
        raise RuntimeError(f"There is already a server running at localhost:{port}")

    redis_save_exists = os.path.isfile(
        "redis.db" if not directory else os.path.join(directory, "redis.db"),
    )

    # to allow connections from other machines we need a default user password
    redis_command = f"redis-server --port {str(port)} --dbfilename redis.db --requirepass {settings.BEFLOW_REDIS_PASSWORD}"

    if directory:
        redis_command = f"{redis_command} --dir {directory}"

    if persistent:
        redis_command = (
            f"{redis_command} --save 900 1 --save 300 100 --save 60 200 --save 15 1000"
        )

    redis_process = subprocess.Popen(
        shlex.split(redis_command),
        stderr=stderr_file,
        stdout=stdout_file,
        preexec_fn=os.setpgrp,
    )

    if terminate_at_exit:
        atexit.register(functools.partial(_cleanup_redis, redis_process))

    timeout = True

    for i in range(0, 60):
        if is_redis_available(
            host="localhost", port=port, password=settings.BEFLOW_REDIS_PASSWORD
        ):
            timeout = False
            break

        time.sleep(1.0)

    if timeout:
        raise RuntimeError("The redis server failed to start.")

    try:
        connect_to_redis(
            host="localhost",
            port=port,
            db=settings.BEFLOW_REDIS_DB,
            password=settings.BEFLOW_REDIS_PASSWORD,
            validate=True,
        )
    except RedisNotConfiguredError:
        if redis_save_exists:
            raise

        connection = connect_to_redis(
            host="localhost",
            port=port,
            db=settings.BEFLOW_REDIS_DB,
            password=settings.BEFLOW_REDIS_PASSWORD,
            validate=False,
        )
        connection.set(
            "openff-bespokefit:redis-version",
            expected_redis_config_version(),
        )

    return redis_process
