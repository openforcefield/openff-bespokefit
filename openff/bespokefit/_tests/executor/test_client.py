import os

import pytest
from fastapi import HTTPException

from openff.bespokefit.executor import BespokeExecutor, BespokeFitClient
from openff.bespokefit.utilities._settings import Settings


def test_authentication(tmpdir):
    settings = Settings()
    print(settings)
    with settings.apply_env():
        executor = BespokeExecutor(
            n_fragmenter_workers=0,
            n_qc_compute_workers=0,
            n_optimizer_workers=0,
            directory=os.path.join(tmpdir, "mock-exe-dir"),
            launch_redis_if_unavailable=False,
        )
        with executor:
            client = BespokeFitClient(settings=settings)
            # make sure we can access the server
            _ = client.list_optimizations()
            # now change the token and try again
            settings.BEFLOW_API_TOKEN = "wrong-token"
            client = BespokeFitClient(settings=settings)
            with pytest.raises(HTTPException):
                _ = client.list_optimizations()
