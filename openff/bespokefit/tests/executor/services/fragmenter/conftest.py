from importlib import reload

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from openff.bespokefit.executor.services.fragmenter import app, worker
from openff.bespokefit.tests.executor import patch_settings


@pytest.fixture(scope="module")
def fragmenter_client() -> TestClient:
    mock_app = FastAPI(title="fragmenter")
    mock_app.include_router(app.router)

    return TestClient(mock_app)


@pytest.fixture(scope="module", autouse=True)
def configure_redis(redis_connection):
    with patch_settings(redis_connection):
        reload(worker)
        yield
