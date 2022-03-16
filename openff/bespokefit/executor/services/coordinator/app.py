import asyncio
import logging
import os
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
)
from openff.bespokefit.executor.services.coordinator.storage import (
    create_task,
    get_n_tasks,
    get_task,
    get_task_ids,
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


@router.get("/" + __settings.BEFLOW_COORDINATOR_PREFIX)
def get_optimizations(skip: int = 0, limit: int = 1000) -> CoordinatorGETPageResponse:
    """Retrieves all bespoke optimizations that have been submitted to this server."""

    task_ids = get_task_ids(skip, limit)
    n_total_tasks = get_n_tasks()

    contents = [
        Link(
            self=(
                f"{__settings.BEFLOW_API_V1_STR}/"
                f"{__settings.BEFLOW_COORDINATOR_PREFIX}/"
                f"{task_id}"
            ),
            id=str(task_id),
        )
        for task_id in task_ids
    ]

    prev_index = max(0, skip - limit)
    next_index = min(n_total_tasks, skip + limit)

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
        if (next_index <= skip or next_index == n_total_tasks)
        else (
            f"{__settings.BEFLOW_API_V1_STR}/"
            f"{__settings.BEFLOW_COORDINATOR_PREFIX}?skip={next_index}&limit={limit}"
        ),
        contents=contents,
    )


@router.get("/" + __settings.BEFLOW_COORDINATOR_PREFIX + "/{optimization_id}")
def get_optimization(optimization_id: int) -> CoordinatorGETResponse:
    """Retrieves a bespoke optimization that has been submitted to this server
    using its unique id."""

    try:
        response = CoordinatorGETResponse.from_task(get_task(optimization_id))
    except IndexError:
        raise HTTPException(status_code=404, detail=f"{optimization_id} not found")

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

    task_id = create_task(body.input_schema)

    return CoordinatorPOSTResponse(
        id=str(task_id),
        self=(
            f"{__settings.BEFLOW_API_V1_STR}/"
            f"{__settings.BEFLOW_COORDINATOR_PREFIX}/{task_id}"
        ),
    )


@router.get(__GET_TASK_IMAGE_ENDPOINT)
async def get_molecule_image(optimization_id: int):
    """Render the molecule associated with a particular bespoke optimization to an
    SVG file."""

    try:
        task = get_task(optimization_id)
    except IndexError:
        raise HTTPException(status_code=404, detail=f"{optimization_id} not found")

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

        except BaseException:

            _logger.exception(
                "Exception raised by the main loop. This should never happen."
            )

            os.kill(os.getpid(), signal.SIGINT)

    _worker_task.add_done_callback(_handle_task_result)


@router.on_event("shutdown")
def shutdown():

    if _worker_task is not None:
        _worker_task.cancel()
