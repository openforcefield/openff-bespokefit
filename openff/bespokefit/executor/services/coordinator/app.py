import asyncio
import logging
import os
import pickle
import signal
import urllib.parse
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from openff.toolkit.topology import Molecule

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.coordinator import worker
from openff.bespokefit.executor.services.coordinator.models import (
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
from openff.bespokefit.executor.utilities.depiction import smiles_to_image

router = APIRouter()

_logger = logging.getLogger(__name__)

_worker_task: Optional[asyncio.Future] = None


@router.get("/" + settings.BEFLOW_COORDINATOR_PREFIX + "/{optimization_id}")
def get_optimization(optimization_id: str) -> CoordinatorGETResponse:
    """Retrieves a bespoke optimization that has been submitted to this server
    using its unique id."""

    task_pickle = worker.redis_connection.get(
        f"coordinator:optimization:{optimization_id}"
    )

    if task_pickle is None:
        raise HTTPException(status_code=404, detail=f"{optimization_id} not found")

    task = CoordinatorTask.parse_obj(pickle.loads(task_pickle))

    return CoordinatorGETResponse.from_task(task)


@router.post("/" + settings.BEFLOW_COORDINATOR_PREFIX)
def post_optimization(body: CoordinatorPOSTBody) -> CoordinatorPOSTResponse:
    """Submit a bespoke optimization to be performed by the server."""

    try:
        # Make sure the input SMILES does not have any atoms mapped as these may
        # cause issues for certain stages such as fragmentation.
        molecule = Molecule.from_smiles(body.input_schema.smiles)
        molecule.properties.pop("atom_map", None)

        body.input_schema.smiles = molecule.to_smiles(mapped=True)
    except BaseException:
        # TODO: Custom exception handling rather than 500 error. 400 / 402?
        raise

    task_id = worker.redis_connection.incr("coordinator:id-counter")
    task_key = f"coordinator:optimization:{task_id}"

    task = CoordinatorTask(
        id=task_id,
        input_schema=body.input_schema,
        pending_stages=[FragmentationStage(), QCGenerationStage(), OptimizationStage()],
    )

    worker.redis_connection.set(task_key, pickle.dumps(task.dict()))
    worker.redis_connection.zadd("coordinator:optimizations", {task_key: task_id})

    return CoordinatorPOSTResponse(optimization_id=task_id)


@router.get("/" + settings.BEFLOW_COORDINATOR_PREFIX + "s")
def get_optimizations(skip: int = 0, limit: int = 10) -> List[CoordinatorGETResponse]:
    """Retrieves all bespoke optimizations that have been submitted to this server."""

    optimization_keys = worker.redis_connection.zrange(
        "coordinator:optimizations", skip * limit, (skip + 1) * limit - 1
    )

    response = []

    for optimization_key in optimization_keys:

        task_pickle = worker.redis_connection.get(optimization_key)

        if task_pickle is None:
            raise HTTPException(status_code=404, detail=f"{optimization_key} not found")

        task = CoordinatorTask.parse_obj(pickle.loads(task_pickle))
        response.append(CoordinatorGETResponse.from_task(task))

    return response


@router.get("/" + settings.BEFLOW_COORDINATOR_PREFIX + "/{optimization_id}/image")
async def get_molecule_image(optimization_id: str):
    """Render the molecule associated with a particular bespoke optimization to an
    SVG file."""

    task_pickle = worker.redis_connection.get(
        f"coordinator:optimization:{optimization_id}"
    )

    if task_pickle is None:
        raise HTTPException(status_code=404, detail=f"{optimization_id} not found")

    task = CoordinatorTask.parse_obj(pickle.loads(task_pickle))

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
