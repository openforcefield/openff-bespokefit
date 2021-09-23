from contextlib import contextmanager

import redis

from openff.bespokefit.executor.services import settings

try:
    from pytest_cov.embed import cleanup_on_sigterm
except ImportError:
    pass
else:
    cleanup_on_sigterm()


@contextmanager
def patch_settings(redis_connection: redis.Redis):

    old_settings = settings.copy(deep=True)

    settings.BEFLOW_REDIS_ADDRESS = redis_connection.connection_pool.connection_kwargs[
        "host"
    ]
    settings.BEFLOW_REDIS_PORT = redis_connection.connection_pool.connection_kwargs[
        "port"
    ]
    settings.BEFLOW_REDIS_DB = redis_connection.connection_pool.connection_kwargs["db"]

    yield

    settings.BEFLOW_REDIS_ADDRESS = old_settings.BEFLOW_REDIS_ADDRESS
    settings.BEFLOW_REDIS_PORT = old_settings.BEFLOW_REDIS_PORT
    settings.BEFLOW_REDIS_DB = old_settings.BEFLOW_REDIS_DB
