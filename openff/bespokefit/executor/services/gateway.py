import importlib
import os
import time
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from typing import Optional

import requests
import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from starlette.middleware.cors import CORSMiddleware

from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.utilities.tempcd import temporary_cd


def __load_router(path: str) -> APIRouter:
    path_split = path.split(":")
    assert (
        len(path_split) == 2
    ), "router paths should have the form 'module.path:router_name'"

    import_path, router_name = path_split

    router_module = importlib.import_module(import_path)
    router = getattr(router_module, router_name)

    return router


__settings = current_settings()


def check_token(request: Request) -> bool:
    """A simple authentication check."""
    token = request.headers["bespokefit-token"]
    # load the current key from the env and check
    if token != current_settings().BEFLOW_API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


app = FastAPI(
    title="openff-bespoke",
    openapi_url=f"{__settings.BEFLOW_API_V1_STR}/openapi.json",
    docs_url=f"{__settings.BEFLOW_API_V1_STR}/docs",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(
    prefix=__settings.BEFLOW_API_V1_STR, dependencies=[Depends(check_token)]
)
api_router.get("")(lambda: {})

api_router.include_router(__load_router(__settings.BEFLOW_COORDINATOR_ROUTER))
api_router.include_router(
    __load_router(__settings.BEFLOW_FRAGMENTER_ROUTER), tags=["fragmenter"]
)
api_router.include_router(
    __load_router(__settings.BEFLOW_QC_COMPUTE_ROUTER), tags=["qcgenerator"]
)
api_router.include_router(
    __load_router(__settings.BEFLOW_OPTIMIZER_ROUTER), tags=["optimizer"]
)

app.include_router(api_router)


@contextmanager
def _output_redirect(log_file: Optional[str] = None):
    if log_file is None:
        yield
        return

    with open(log_file, "a") as file:
        with redirect_stdout(file):
            with redirect_stderr(file):
                yield


def launch(directory: Optional[str] = None, log_file: Optional[str] = None):
    if directory is not None and len(directory) > 0:
        os.makedirs(directory, exist_ok=True)

    with temporary_cd(directory):
        with _output_redirect(log_file):
            uvicorn.run(
                "openff.bespokefit.executor.services.gateway:app",
                host="0.0.0.0",
                port=__settings.BEFLOW_GATEWAY_PORT,
                log_level=__settings.BEFLOW_GATEWAY_LOG_LEVEL,
            )


def wait_for_gateway(n_retries: int = 40):
    timeout = True
    # load the settings again to get the most recent token
    settings = current_settings()
    for _ in range(n_retries):
        try:
            ping = requests.get(
                f"http://127.0.0.1:{settings.BEFLOW_GATEWAY_PORT}{settings.BEFLOW_API_V1_STR}",
                headers={"bespokefit-token": settings.BEFLOW_API_TOKEN},
            )
            ping.raise_for_status()

        except IOError:
            time.sleep(0.25)
            continue

        timeout = False
        break

    if timeout:
        raise RuntimeError("The gateway could not be reached.")
