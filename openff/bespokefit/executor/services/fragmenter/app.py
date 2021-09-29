import json

from fastapi import APIRouter
from fastapi.responses import Response
from openff.fragmenter.depiction import _oe_render_fragment
from openff.fragmenter.fragment import FragmentationResult

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.fragmenter import worker
from openff.bespokefit.executor.services.fragmenter.models import (
    FragmenterGETResponse,
    FragmenterPOSTBody,
    FragmenterPOSTResponse,
)
from openff.bespokefit.executor.utilities.celery import get_task_information
from openff.bespokefit.executor.utilities.depiction import IMAGE_UNAVAILABLE_SVG

router = APIRouter()


@router.get("/" + settings.BEFLOW_FRAGMENTER_PREFIX + "/{fragmentation_id}")
def get_fragment(fragmentation_id: str) -> FragmenterGETResponse:

    task_info = get_task_information(worker.celery_app, fragmentation_id)

    return FragmenterGETResponse(
        fragmentation_id=fragmentation_id,
        fragmentation_status=task_info["status"],
        fragmentation_result=task_info["result"],
        fragmentation_error=json.dumps(task_info["error"]),
    )


@router.post("/" + settings.BEFLOW_FRAGMENTER_PREFIX)
def post_fragment(body: FragmenterPOSTBody) -> FragmenterPOSTResponse:
    # We use celery delay method in order to enqueue the task with the given
    # parameters

    task = worker.fragment.delay(
        cmiles=body.cmiles,
        fragmenter_json=body.fragmenter.json(),
        target_bond_smarts=body.target_bond_smarts,
    )
    return FragmenterPOSTResponse(fragmentation_id=task.id)


@router.get(
    "/"
    + settings.BEFLOW_FRAGMENTER_PREFIX
    + "/{fragmentation_id}/fragment/{fragment_id}/image"
)
def get_fragment_image(fragmentation_id: str, fragment_id: int) -> Response:

    task_info = get_task_information(worker.celery_app, fragmentation_id)

    if task_info["status"] != "success":
        return Response(IMAGE_UNAVAILABLE_SVG, media_type="image/svg+xml")

    result = FragmentationResult.parse_obj(task_info["result"])

    if fragment_id < 0 or fragment_id >= len(result.fragments):
        return Response(IMAGE_UNAVAILABLE_SVG, media_type="image/svg+xml")

    fragment = result.fragments[fragment_id]

    svg_content = _oe_render_fragment(
        result.parent_molecule,
        fragment.molecule,
        fragment.bond_indices,
        image_width=200,
        image_height=200,
    )

    return Response(svg_content, media_type="image/svg+xml")
