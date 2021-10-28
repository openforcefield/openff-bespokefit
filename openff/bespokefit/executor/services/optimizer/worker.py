from typing import Union

import redis
from pydantic import parse_raw_as
from qcelemental.util import serialize

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.utilities.celery import configure_celery_app
from openff.bespokefit.optimizers import get_optimizer
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults

redis_connection = redis.Redis(
    host=settings.BEFLOW_REDIS_ADDRESS,
    port=settings.BEFLOW_REDIS_PORT,
    db=settings.BEFLOW_REDIS_DB,
)
celery_app = configure_celery_app("optimizer", redis_connection)


@celery_app.task(bind=True, acks_late=True)
def optimize(self, optimization_input_json: str) -> str:

    from openff.toolkit.typing.engines.smirnoff import ForceField

    input_schema = parse_raw_as(
        Union[BespokeOptimizationSchema], optimization_input_json
    )
    input_schema.id = self.request.id

    input_force_field = ForceField(input_schema.initial_force_field)

    stage_results = []

    for stage in input_schema.stages:

        optimizer = get_optimizer(stage.optimizer.type)
        result = optimizer.optimize(
            stage, input_force_field, keep_files=settings.BEFLOW_KEEP_FILES
        )

        stage_results.append(result)

        if result.status != "success":
            break

        input_force_field = ForceField(
            ForceField(
                result.refit_force_field, allow_cosmetic_attributes=True
            ).to_string(discard_cosmetic_attributes=True)
        )

    return serialize(
        BespokeOptimizationResults(input_schema=input_schema, stages=stage_results),
        encoding="json",
    )
