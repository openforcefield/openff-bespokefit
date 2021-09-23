import atexit
import functools
import shlex
import shutil
import subprocess
import time
from typing import IO, Optional, Union

import redis


def is_redis_available(host: str, port: int = 6379) -> bool:
    """Returns whether a server running on the local host on a particular port is
    available.
    """

    redis_client = redis.Redis(host=host, port=port)

    try:
        redis_client.get("null")

    except (redis.exceptions.ConnectionError, redis.exceptions.BusyLoadingError):
        return False

    return True


def _cleanup_redis(redis_process: subprocess.Popen):
    redis_process.terminate()


def launch_redis(
    port: int = 6379,
    stderr_file: Optional[Union[IO, int]] = None,
    stdout_file: Optional[Union[IO, int]] = None,
    directory: Optional[str] = None,
    persistent: bool = True,
):

    redis_server_path = shutil.which("redis-server")

    if redis_server_path is None:

        raise RuntimeError(
            "The `redis-server` command could not be found. Please make sure `redis` is "
            "correctly installed."
        )

    redis_cli_path = shutil.which("redis-cli")

    if redis_cli_path is None:

        raise RuntimeError(
            "The `redis-cli` command could not be found. Please make sure `redis` is "
            "correctly installed."
        )

    if is_redis_available("localhost", port):
        raise RuntimeError(f"There is already a server running at localhost:{port}")

    redis_command = f"redis-server --port {str(port)} --dbfilename redis.db"

    if directory:
        redis_command = f"{redis_command} --dir {directory}"

    if persistent:
        redis_command = (
            f"{redis_command} --save 900 1 --save 300 100 --save 60 200 --save 15 1000"
        )

    redis_process = subprocess.Popen(
        shlex.split(redis_command), stderr=stderr_file, stdout=stdout_file
    )
    atexit.register(functools.partial(_cleanup_redis, redis_process))

    timeout = True

    for i in range(0, 60):

        if is_redis_available("localhost", port):
            timeout = False
            break

        time.sleep(1.0)

    if timeout:
        raise RuntimeError("The redis server failed to start.")

    return redis_process
