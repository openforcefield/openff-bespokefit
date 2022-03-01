import asyncio
import logging
import os
import pickle
import signal
import urllib.parse
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from openff.toolkit.topology import Molecule

from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.services.coordinator import worker
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETPageResponse,
    CoordinatorGETResponse,
    CoordinatorPOSTBody,
    CoordinatorPOSTResponse,
    CoordinatorTask,
)
from openff.bespokefit.executor.services.coordinator.stages import (
    FragmentationStage,
    OptimizationStage,
    QCGenerationStage,
)
from openff.bespokefit.executor.services.models import Link
from openff.bespokefit.executor.utilities.depiction import smiles_to_image

router = APIRouter()

_logger = logging.getLogger(__name__)
_worker_task: Optional[asyncio.Future] = None

__settings = current_settings()

__GET_TASK_IMAGE_ENDPOINT = (
    "/" + __settings.BEFLOW_COORDINATOR_PREFIX + "/{optimization_id}/image"
)


def _get_task(
    optimization_id: Optional[str] = None, optimization_key: Optional[str] = None
) -> CoordinatorTask:

    assert (optimization_id is None or optimization_key is None) and (
        optimization_id is not None or optimization_key is not None
    ), "the key and id are mutually exclusive arguments"

    if optimization_id is not None:
        optimization_key = f"coordinator:optimization:{optimization_id}"

    task_pickle = worker.redis_connection.get(optimization_key)

    if task_pickle is None:
        raise HTTPException(status_code=404, detail=f"{optimization_key} not found")

    return CoordinatorTask.parse_obj(pickle.loads(task_pickle))


@router.get("/" + __settings.BEFLOW_COORDINATOR_PREFIX)
def get_optimizations(skip: int = 0, limit: int = 1000) -> CoordinatorGETPageResponse:
    """Retrieves all bespoke optimizations that have been submitted to this server."""

    n_optimizations = worker.redis_connection.zcount(
        "coordinator:optimizations", 0, 999999999
    )

    optimization_keys = worker.redis_connection.zrange(
        "coordinator:optimizations", skip * limit, (skip + 1) * limit - 1
    )
    optimization_ids = [
        optimization_key.decode().split(":")[-1]
        for optimization_key in optimization_keys
    ]

    contents = [
        Link(
            self=(
                f"{__settings.BEFLOW_API_V1_STR}/"
                f"{__settings.BEFLOW_COORDINATOR_PREFIX}/"
                f"{optimization_id}"
            ),
            id=optimization_id,
        )
        for optimization_id in optimization_ids
    ]

    prev_index = max(0, skip - limit)
    next_index = min(n_optimizations, skip + limit)

    return CoordinatorGETPageResponse(
        self=(
            f"{__settings.BEFLOW_API_V1_STR}/"
            f"{__settings.BEFLOW_COORDINATOR_PREFIX}?skip={skip}&limit={limit}"
        ),
        prev=None
        if prev_index >= skip
        else (
            f"{__settings.BEFLOW_API_V1_STR}/"
            f"{__settings.BEFLOW_COORDINATOR_PREFIX}?skip={prev_index}&limit={limit}"
        ),
        next=None
        if (next_index <= skip or next_index == n_optimizations)
        else (
            f"{__settings.BEFLOW_API_V1_STR}/"
            f"{__settings.BEFLOW_COORDINATOR_PREFIX}?skip={next_index}&limit={limit}"
        ),
        contents=contents,
    )


@router.get("/" + __settings.BEFLOW_COORDINATOR_PREFIX + "/{optimization_id}")
def get_optimization(optimization_id: str) -> CoordinatorGETResponse:
    """Retrieves a bespoke optimization that has been submitted to this server
    using its unique id."""

    response = CoordinatorGETResponse.from_task(
        _get_task(optimization_id=optimization_id)
    )
    response.links = {
        "image": (
            __settings.BEFLOW_API_V1_STR
            + __GET_TASK_IMAGE_ENDPOINT.format(optimization_id=optimization_id)
        )
    }

    return response


@router.post("/" + __settings.BEFLOW_COORDINATOR_PREFIX)
def post_optimization(body: CoordinatorPOSTBody) -> CoordinatorPOSTResponse:
    """Submit a bespoke optimization to be performed by the server."""

    try:
        # Make sure the input SMILES does not have any atoms mapped as these may
        # cause issues for certain stages such as fragmentation.
        molecule = Molecule.from_smiles(body.input_schema.smiles)
        molecule.properties.pop("atom_map", None)

        body.input_schema.smiles = molecule.to_smiles(mapped=True)
    except BaseException as e:

        raise HTTPException(
            status_code=400, detail="molecule could not be understood"
        ) from e

    task_id = worker.redis_connection.incr("coordinator:id-counter")
    task_key = f"coordinator:optimization:{task_id}"

    task = CoordinatorTask(
        id=task_id,
        input_schema=body.input_schema,
        pending_stages=[FragmentationStage(), QCGenerationStage(), OptimizationStage()],
    )
    task.input_schema.id = task_id

    worker.redis_connection.set(task_key, pickle.dumps(task.dict()))
    worker.redis_connection.zadd("coordinator:optimizations", {task_key: task_id})

    return CoordinatorPOSTResponse(
        id=task_id,
        self=(
            f"{__settings.BEFLOW_API_V1_STR}/"
            f"{__settings.BEFLOW_COORDINATOR_PREFIX}/{task.id}"
        ),
    )


@router.get(__GET_TASK_IMAGE_ENDPOINT)
async def get_molecule_image(optimization_id: str):
    """Render the molecule associated with a particular bespoke optimization to an
    SVG file."""

    task = _get_task(optimization_id=optimization_id)

    svg_content = smiles_to_image(urllib.parse.unquote(task.input_schema.smiles))
    svg_response = Response(svg_content, media_type="image/svg+xml")

    return svg_response


@router.on_event("startup")
def startup():
    main_loop = asyncio.get_event_loop()

    global _worker_task
    _worker_task = asyncio.ensure_future(worker.cycle(), loop=main_loop)

    def _handle_task_result(task: asyncio.Task) -> None:

        # noinspection PyBroadException
        try:
            task.result()

        except asyncio.CancelledError:
            pass

        except Exception:

            _logger.exception(
                "Exception raised by the main loop. This should never happen."
            )

            os.kill(os.getpid(), signal.SIGINT)

    _worker_task.add_done_callback(_handle_task_result)


@router.on_event("shutdown")
def shutdown():

    if _worker_task is not None:
        _worker_task.cancel()
