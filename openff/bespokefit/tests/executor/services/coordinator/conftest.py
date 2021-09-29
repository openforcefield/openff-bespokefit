from importlib import reload

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from openff.bespokefit.executor.services.coordinator import app, worker
from openff.bespokefit.tests.executor import patch_settings


@pytest.fixture(scope="module")
def coordinator_client() -> TestClient:

    mock_app = FastAPI(title="coordinator")
    mock_app.include_router(app.router)

    old_cycle = worker.cycle

    async def mock_cycle():
        return

    worker.cycle = mock_cycle

    try:
        yield TestClient(mock_app)

    finally:
        worker.cycle = old_cycle


@pytest.fixture(scope="module", autouse=True)
def configure_redis(redis_connection):

    with patch_settings(redis_connection):

        reload(worker)
        yield
