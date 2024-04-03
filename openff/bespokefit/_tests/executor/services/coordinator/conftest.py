from importlib import reload

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from openff.bespokefit._tests.executor import patch_settings
from openff.bespokefit.executor.services.coordinator import app, worker


@pytest.fixture(scope="module")
def coordinator_client() -> TestClient:
    mock_app = FastAPI(title="coordinator")
    mock_app.include_router(app.router)

    return TestClient(mock_app)


@pytest.fixture(scope="module", autouse=True)
def configure_redis(redis_connection):
    with patch_settings(redis_connection):
        reload(worker)
        yield
