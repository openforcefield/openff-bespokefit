import json
from typing import List, Optional, Union

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import parse_obj_as
from qcelemental.models import AtomicResult, OptimizationResult
from qcengine.procedures.torsiondrive import TorsionDriveResult

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.qcgenerator import worker
from openff.bespokefit.executor.services.qcgenerator.models import (
    QCGeneratorGETResponse,
    QCGeneratorPOSTBody,
    QCGeneratorPOSTResponse,
)
from openff.bespokefit.executor.utilities.celery import get_task_information
from openff.bespokefit.executor.utilities.depiction import (
    IMAGE_UNAVAILABLE_SVG,
    smiles_to_image,
)
from openff.bespokefit.schema.tasks import HessianTask, OptimizationTask, Torsion1DTask

router = APIRouter()


def _retrieve_qc_result(qc_calc_id: str, results: bool) -> QCGeneratorGETResponse:

    qc_task_info = get_task_information(worker.celery_app, qc_calc_id)
    qc_calc_type = worker.redis_connection.hget("qcgenerator:types", qc_calc_id)

    # Because QCElemental models contain numpy arrays that aren't natively JSON
    # serializable we need to work with plain dicts of primitive types here.
    # noinspection PyTypeChecker
    return {
        "qc_calc_id": qc_calc_id,
        "qc_calc_status": qc_task_info["status"],
        "qc_calc_type": qc_calc_type.decode(),
        "qc_calc_result": None if not results else qc_task_info["result"],
        "qc_calc_error": json.dumps(qc_task_info["error"]),
    }


@router.get("/" + settings.BEFLOW_QC_COMPUTE_PREFIX + "s")
def get_qc_results(
    ids: Optional[List[str]] = Query(None), results: bool = True
) -> List[QCGeneratorGETResponse]:

    if ids is None:
        raise NotImplementedError()

    return [_retrieve_qc_result(qc_calc_id, results) for qc_calc_id in ids]


@router.get("/" + settings.BEFLOW_QC_COMPUTE_PREFIX + "/{qc_calc_id}")
def get_qc_result(qc_calc_id: str, results: bool = True) -> QCGeneratorGETResponse:
    return _retrieve_qc_result(qc_calc_id, results)


@router.post("/" + settings.BEFLOW_QC_COMPUTE_PREFIX)
def post_qc_result(body: QCGeneratorPOSTBody) -> QCGeneratorPOSTResponse:

    if isinstance(body.input_schema, Torsion1DTask):
        compute = worker.compute_torsion_drive
    elif isinstance(body.input_schema, OptimizationTask):
        compute = worker.compute_optimization
    elif isinstance(body.input_schema, HessianTask):
        compute = worker.compute_hessian
    else:
        raise NotImplementedError()

    task = compute.delay(task_json=body.input_schema.json())

    worker.redis_connection.hset("qcgenerator:types", task.id, body.input_schema.type)

    return QCGeneratorPOSTResponse(
        qc_calc_id=task.id, qc_calc_type=body.input_schema.type
    )


@router.get("/" + settings.BEFLOW_QC_COMPUTE_PREFIX + "/{qc_calc_id}/image/molecule")
def get_qc_result_molecule_image(qc_calc_id: str):

    task_info = get_task_information(worker.celery_app, qc_calc_id)

    if task_info["status"] != "success":
        return Response(IMAGE_UNAVAILABLE_SVG, media_type="image/svg+xml")

    qc_result = parse_obj_as(
        Union[TorsionDriveResult, OptimizationResult, AtomicResult], task_info["result"]
    )

    if isinstance(qc_result, (OptimizationResult, TorsionDriveResult)):

        highlight_atoms = (
            None
            if isinstance(qc_result, OptimizationResult)
            else tuple(i + 1 for i in qc_result.keywords["dihedrals"][0])
        )

        svg_content = smiles_to_image(
            qc_result.initial_molecule.extras[
                "canonical_isomeric_explicit_hydrogen_mapped_smiles"
            ],
            highlight_atoms=highlight_atoms,
        )

    elif isinstance(qc_result, AtomicResult):

        svg_content = smiles_to_image(
            qc_result.molecule.extras[
                "canonical_isomeric_explicit_hydrogen_mapped_smiles"
            ]
        )

    else:
        raise NotImplementedError()

    return Response(svg_content, media_type="image/svg+xml")
