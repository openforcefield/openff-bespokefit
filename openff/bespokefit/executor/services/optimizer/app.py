import json

from fastapi import APIRouter
from qcelemental.util import serialize

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.optimizer import worker
from openff.bespokefit.executor.services.optimizer.models import (
    OptimizerGETResponse,
    OptimizerPOSTBody,
    OptimizerPOSTResponse,
)
from openff.bespokefit.executor.utilities.celery import get_task_information

router = APIRouter()

__GET_ENDPOINT = "/" + settings.BEFLOW_OPTIMIZER_PREFIX + "/{optimization_id}"


@router.get(__GET_ENDPOINT)
def get_optimization(optimization_id: str) -> OptimizerGETResponse:

    task_info = get_task_information(worker.celery_app, optimization_id)

    # noinspection PyTypeChecker
    return {
        "id": optimization_id,
        "self": settings.BEFLOW_API_V1_STR
        + __GET_ENDPOINT.format(optimization_id=optimization_id),
        "status": task_info["status"],
        "result": task_info["result"],
        "error": json.dumps(task_info["error"]),
    }


@router.post("/" + settings.BEFLOW_OPTIMIZER_PREFIX)
def post_optimization(body: OptimizerPOSTBody) -> OptimizerPOSTResponse:
    # We use celery delay method in order to enqueue the task with the given
    # parameters

    task = worker.optimize.delay(
        optimization_input_json=serialize(body.input_schema, "json")
    )
    return OptimizerPOSTResponse(
        id=task.id,
        self=settings.BEFLOW_API_V1_STR
        + __GET_ENDPOINT.format(optimization_id=task.id),
    )
