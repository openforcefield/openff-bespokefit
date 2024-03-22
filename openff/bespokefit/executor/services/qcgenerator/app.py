"""The qc generation app."""

import json
from typing import Optional, Union

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import parse_obj_as
from qcelemental.models import AtomicResult, OptimizationResult
from qcengine.procedures.torsiondrive import TorsionDriveResult

from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.services.qcgenerator import worker
from openff.bespokefit.executor.services.qcgenerator.cache import cached_compute_task
from openff.bespokefit.executor.services.qcgenerator.models import (
    QCGeneratorGETPageResponse,
    QCGeneratorGETResponse,
    QCGeneratorPOSTBody,
    QCGeneratorPOSTResponse,
)
from openff.bespokefit.executor.utilities.celery import get_task_information
from openff.bespokefit.executor.utilities.depiction import (
    IMAGE_UNAVAILABLE_SVG,
    smiles_to_image,
)
from openff.bespokefit.executor.utilities.redis import connect_to_default_redis

router = APIRouter()

__settings = current_settings()

__GET_ENDPOINT = "/" + __settings.BEFLOW_QC_COMPUTE_PREFIX + "/{qc_calc_id}"
__GET_IMAGE_ENDPOINT = (
    "/" + __settings.BEFLOW_QC_COMPUTE_PREFIX + "/{qc_calc_id}/image/molecule"
)


def _retrieve_qc_result(qc_calc_id: str, results: bool) -> QCGeneratorGETResponse:
    redis_connection = connect_to_default_redis()

    qc_task_info = get_task_information(worker.celery_app, qc_calc_id)
    qc_calc_type = redis_connection.hget("qcgenerator:types", qc_calc_id)

    # Because QCElemental models contain numpy arrays that aren't natively JSON
    # serializable we need to work with plain dicts of primitive types here.
    # noinspection PyTypeChecker
    return {
        "id": qc_calc_id,
        "self": __settings.BEFLOW_API_V1_STR
        + __GET_ENDPOINT.format(qc_calc_id=qc_calc_id),
        "status": qc_task_info["status"],
        "type": qc_calc_type.decode(),
        "result": None if not results else qc_task_info["result"],
        "error": json.dumps(qc_task_info["error"]),
        "_links": {
            "image": (
                __settings.BEFLOW_API_V1_STR
                + __GET_IMAGE_ENDPOINT.format(qc_calc_id=qc_calc_id)
            ),
        },
    }


@router.get("/" + __settings.BEFLOW_QC_COMPUTE_PREFIX)
def get_qc_results(
    ids: Optional[list[str]] = Query(None),
    results: bool = True,
) -> QCGeneratorGETPageResponse:
    """Get QC results."""
    if ids is None:
        raise NotImplementedError()

    response = QCGeneratorGETPageResponse(
        self="/" + __settings.BEFLOW_QC_COMPUTE_PREFIX,
        prev=None,
        next=None,
        contents=[_retrieve_qc_result(qc_calc_id, results) for qc_calc_id in ids],
    )

    return response


@router.get(__GET_ENDPOINT)
def get_qc_result(qc_calc_id: str, results: bool = True) -> QCGeneratorGETResponse:
    """Route a QC result to GET."""
    response = _retrieve_qc_result(qc_calc_id, results)
    return response


@router.post("/" + __settings.BEFLOW_QC_COMPUTE_PREFIX)
def post_qc_result(body: QCGeneratorPOSTBody) -> QCGeneratorPOSTResponse:
    """Route the the QC result as an image to POST."""
    redis_connection = connect_to_default_redis()
    task_id = cached_compute_task(body.input_schema, redis_connection)

    return QCGeneratorPOSTResponse(
        id=task_id,
        self=__settings.BEFLOW_API_V1_STR + __GET_ENDPOINT.format(qc_calc_id=task_id),
    )


@router.get(__GET_IMAGE_ENDPOINT)
def get_qc_result_molecule_image(qc_calc_id: str):
    """Route the QC result as an image to GET."""
    task_info = get_task_information(worker.celery_app, qc_calc_id)

    if task_info["status"] != "success":
        return Response(IMAGE_UNAVAILABLE_SVG, media_type="image/svg+xml")

    qc_result = parse_obj_as(
        Union[TorsionDriveResult, OptimizationResult, AtomicResult],
        task_info["result"],
    )

    if isinstance(qc_result, (OptimizationResult, TorsionDriveResult)):
        highlight_atoms = (
            None
            if isinstance(qc_result, OptimizationResult)
            else tuple(i + 1 for i in qc_result.keywords.dihedrals[0])
        )

        svg_content = smiles_to_image(
            qc_result.initial_molecule[0].extras[
                "canonical_isomeric_explicit_hydrogen_mapped_smiles"
            ],
            highlight_atoms=highlight_atoms,
        )

    elif isinstance(qc_result, AtomicResult):
        svg_content = smiles_to_image(
            qc_result.molecule.extras[
                "canonical_isomeric_explicit_hydrogen_mapped_smiles"
            ],
        )

    else:
        raise NotImplementedError()

    return Response(svg_content, media_type="image/svg+xml")
