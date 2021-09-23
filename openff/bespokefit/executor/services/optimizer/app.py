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


@router.get("/" + settings.BEFLOW_OPTIMIZER_PREFIX + "/{optimization_id}")
def get_optimization(optimization_id: str) -> OptimizerGETResponse:

    task_info = get_task_information(worker.celery_app, optimization_id)

    # noinspection PyTypeChecker
    return {
        "optimization_id": optimization_id,
        "optimization_status": task_info["status"],
        "optimization_result": task_info["result"],
        "optimization_error": json.dumps(task_info["error"]),
    }


@router.post("/" + settings.BEFLOW_OPTIMIZER_PREFIX)
def post_optimization(body: OptimizerPOSTBody) -> OptimizerPOSTResponse:
    # We use celery delay method in order to enqueue the task with the given
    # parameters

    task = worker.optimize.delay(
        optimization_input_json=serialize(body.input_schema, "json")
    )
    return OptimizerPOSTResponse(optimization_id=task.id)
