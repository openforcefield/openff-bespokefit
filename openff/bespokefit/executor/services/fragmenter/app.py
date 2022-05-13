import json

from fastapi import APIRouter
from fastapi.responses import Response
from openff.fragmenter.fragment import FragmentationResult

from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.services.fragmenter import worker
from openff.bespokefit.executor.services.fragmenter.cache import (
    cached_fragmentation_task,
)
from openff.bespokefit.executor.services.fragmenter.models import (
    FragmenterGETResponse,
    FragmenterPOSTBody,
    FragmenterPOSTResponse,
)
from openff.bespokefit.executor.utilities.celery import get_task_information
from openff.bespokefit.executor.utilities.depiction import IMAGE_UNAVAILABLE_SVG
from openff.bespokefit.executor.utilities.redis import connect_to_default_redis

router = APIRouter()

__settings = current_settings()

__GET_ENDPOINT = "/" + __settings.BEFLOW_FRAGMENTER_PREFIX + "/{fragmentation_id}"
__GET_FRAGMENT_IMAGE_ENDPOINT = (
    "/"
    + __settings.BEFLOW_FRAGMENTER_PREFIX
    + "/{fragmentation_id}/fragment/{fragment_id}/image"
)


@router.get(__GET_ENDPOINT)
def get_fragment(fragmentation_id: str) -> FragmenterGETResponse:

    task_info = get_task_information(worker.celery_app, fragmentation_id)
    task_result = task_info["result"]

    return FragmenterGETResponse(
        id=fragmentation_id,
        self=__settings.BEFLOW_API_V1_STR
        + __GET_ENDPOINT.format(fragmentation_id=fragmentation_id),
        status=task_info["status"],
        result=task_result,
        error=json.dumps(task_info["error"]),
        _links={
            f"fragment-{i}-image": (
                __settings.BEFLOW_API_V1_STR
                + __GET_FRAGMENT_IMAGE_ENDPOINT.format(
                    fragmentation_id=fragmentation_id, fragment_id=i
                )
            )
            for i, fragment in enumerate(
                [] if task_result is None else task_result["fragments"]
            )
        },
    )


@router.post("/" + __settings.BEFLOW_FRAGMENTER_PREFIX)
def post_fragment(body: FragmenterPOSTBody) -> FragmenterPOSTResponse:
    # We use celery delay method in order to enqueue the task with the given
    # parameters

    task_id = cached_fragmentation_task(
        task=body, redis_connection=connect_to_default_redis()
    )
    return FragmenterPOSTResponse(
        id=task_id,
        self=__settings.BEFLOW_API_V1_STR
        + __GET_ENDPOINT.format(fragmentation_id=task_id),
    )


@router.get(__GET_FRAGMENT_IMAGE_ENDPOINT)
def get_fragment_image(fragmentation_id: str, fragment_id: int) -> Response:

    task_info = get_task_information(worker.celery_app, fragmentation_id)

    if task_info["status"] != "success":
        return Response(IMAGE_UNAVAILABLE_SVG, media_type="image/svg+xml")

    result = FragmentationResult.parse_obj(task_info["result"])

    if fragment_id < 0 or fragment_id >= len(result.fragments):
        return Response(IMAGE_UNAVAILABLE_SVG, media_type="image/svg+xml")

    fragment = result.fragments[fragment_id]

    try:
        from openff.fragmenter.depiction import _oe_render_fragment as _render
    except ModuleNotFoundError:
        from openff.fragmenter.depiction import _rd_render_fragment as _render

    svg_content = _render(
        result.parent_molecule,
        fragment.molecule,
        fragment.bond_indices,
        image_width=200,
        image_height=200,
    )

    return Response(svg_content, media_type="image/svg+xml")
