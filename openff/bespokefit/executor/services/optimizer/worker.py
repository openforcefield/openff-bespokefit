from typing import Union

import redis
from openff.bespokefit.optimizers import get_optimizer
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from pydantic import parse_raw_as
from qcelemental.util import serialize

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.utilities.celery import configure_celery_app

redis_connection = redis.Redis(
    host=settings.BEFLOW_REDIS_ADDRESS,
    port=settings.BEFLOW_REDIS_PORT,
    db=settings.BEFLOW_REDIS_DB,
)
celery_app = configure_celery_app("optimizer", redis_connection)


@celery_app.task
def optimize(optimization_input_json: str) -> str:

    input_schema = parse_raw_as(
        Union[BespokeOptimizationSchema], optimization_input_json
    )

    optimizer = get_optimizer(input_schema.optimizer.type)
    result = optimizer.optimize(input_schema, keep_files=True)

    return serialize(result, encoding="json")
