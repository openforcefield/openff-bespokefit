import functools
from multiprocessing import Process

import pytest

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.gateway import app, launch, wait_for_gateway


def test_default_routes_loaded():

    found_routes = [router.path for router in app.routes]

    assert all(
        route in found_routes
        for route in [
            "/api/v1/tasks",
            "/api/v1/fragmentations",
            "/api/v1/optimizations",
            "/api/v1/qc-calcs",
        ]
    )


@pytest.mark.parametrize("directory", [None, "."])
def test_launch(directory):

    process = Process(target=functools.partial(launch, directory))
    process.start()

    wait_for_gateway()

    process.terminate()
    process.join()


def test_wait_for_gateway_timeout(monkeypatch):

    monkeypatch.setattr(settings, "BEFLOW_GATEWAY_PORT", 111)

    with pytest.raises(RuntimeError, match="The gateway could not be reached"):
        wait_for_gateway(n_retries=1)
