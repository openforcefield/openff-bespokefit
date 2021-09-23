import importlib
import os
import time
from typing import Optional

import requests
import uvicorn
from fastapi import APIRouter, FastAPI
from openff.utilities import temporary_cd
from starlette.middleware.cors import CORSMiddleware

from openff.bespokefit.executor.services import settings


def __load_router(path: str) -> APIRouter:

    path_split = path.split(":")
    assert (
        len(path_split) == 2
    ), "router paths should have the form 'module.path:router_name'"

    import_path, router_name = path_split

    router_module = importlib.import_module(import_path)
    router = getattr(router_module, router_name)

    return router


app = FastAPI(
    title="openff-bespoke",
    openapi_url=f"{settings.BEFLOW_API_V1_STR}/openapi.json",
    docs_url=f"{settings.BEFLOW_API_V1_STR}/docs",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix=settings.BEFLOW_API_V1_STR)
api_router.get("")(lambda: {})

api_router.include_router(__load_router(settings.BEFLOW_COORDINATOR_ROUTER))
api_router.include_router(
    __load_router(settings.BEFLOW_FRAGMENTER_ROUTER), tags=["fragmenter"]
)
api_router.include_router(
    __load_router(settings.BEFLOW_QC_COMPUTE_ROUTER), tags=["qcgenerator"]
)
api_router.include_router(
    __load_router(settings.BEFLOW_OPTIMIZER_ROUTER), tags=["optimizer"]
)

app.include_router(api_router)


def launch(directory: Optional[str] = None):

    if directory is not None and len(directory) > 0:
        os.makedirs(directory, exist_ok=True)

    with temporary_cd(directory):

        uvicorn.run(
            "openff.bespokefit.executor.services.gateway:app",
            host="0.0.0.0",
            port=settings.BEFLOW_GATEWAY_PORT,
            log_level=settings.BEFLOW_GATEWAY_LOG_LEVEL,
        )


def wait_for_gateway(n_retries: int = 40):

    timeout = True

    for _ in range(n_retries):

        try:

            ping = requests.get(
                f"http://127.0.0.1:{settings.BEFLOW_GATEWAY_PORT}{settings.BEFLOW_API_V1_STR}"
            )
            ping.raise_for_status()

        except IOError:

            time.sleep(0.25)
            continue

        timeout = False
        break

    if timeout:
        raise RuntimeError("The gateway could not be reached.")
