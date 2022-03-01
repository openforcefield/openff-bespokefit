from contextlib import contextmanager

import redis

from openff.bespokefit.executor.services import Settings

try:
    from pytest_cov.embed import cleanup_on_sigterm
except ImportError:
    pass
else:
    cleanup_on_sigterm()


@contextmanager
def patch_settings(redis_connection: redis.Redis):

    with Settings(
        BEFLOW_REDIS_ADDRESS=redis_connection.connection_pool.connection_kwargs["host"],
        BEFLOW_REDIS_PORT=redis_connection.connection_pool.connection_kwargs["port"],
        BEFLOW_REDIS_DB=redis_connection.connection_pool.connection_kwargs["db"],
    ).apply_env():

        yield
