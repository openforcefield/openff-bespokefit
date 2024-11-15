import os

import pytest
from requests import HTTPError

from openff.bespokefit.executor import BespokeExecutor, BespokeFitClient
from openff.bespokefit.utilities._settings import Settings


def test_token_warning():
    settings = Settings(BEFLOW_API_TOKEN="test")
    with pytest.warns(
        match="Using an API token without an https connection is insecure, consider using https for encrypted comunication."
    ):
        _ = BespokeFitClient(settings=settings)


def test_authentication(tmpdir):
    """Simple authentication test"""
    # set the API key before starting the server
    settings = Settings(BEFLOW_API_TOKEN="secure-key")
    with settings.apply_env():
        executor = BespokeExecutor(
            n_fragmenter_workers=0,
            n_qc_compute_workers=0,
            n_optimizer_workers=0,
            directory=os.path.join(tmpdir, "mock-exe-dir"),
            launch_redis_if_unavailable=True,
        )
        with executor:
            client = BespokeFitClient(settings=settings)
            # make sure we can access the server using the correct key
            _ = client.list_optimizations()
            # now change the token and try again
            settings.BEFLOW_API_TOKEN = "wrong-token"
            client = BespokeFitClient(settings=settings)
            with pytest.raises(HTTPError):
                _ = client.list_optimizations()
            # make sure to shut down the executor
            executor._cleanup_processes()
