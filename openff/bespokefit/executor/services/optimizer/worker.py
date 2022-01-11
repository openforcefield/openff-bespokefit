import os
import shutil
from typing import Union

import redis
from openff.utilities import temporary_cd
from pydantic import parse_raw_as
from qcelemental.util import serialize

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.coordinator.utils import cache_parameters
from openff.bespokefit.executor.utilities.celery import configure_celery_app
from openff.bespokefit.optimizers import get_optimizer
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.results import (
    BespokeOptimizationResults,
    OptimizationStageResults,
)

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
    input_schema.id = self.request.id or input_schema.id

    # some parameters have a cached attribute
    input_force_field = ForceField(
        input_schema.initial_force_field, allow_cosmetic_attributes=True
    )

    stage_results = []

    home = os.getcwd()

    with temporary_cd():
        for i, stage in enumerate(input_schema.stages):

            optimizer = get_optimizer(stage.optimizer.type)
            # If there are no parameters to optimise as they have all been cached mock the result
            if not stage.parameters:
                result = OptimizationStageResults(
                    provenance={"skipped": True},
                    status="success",
                    error=None,
                    refit_force_field=input_force_field.to_string(
                        discard_cosmetic_attributes=True
                    ),
                )
            else:
                result = optimizer.optimize(
                    schema=stage,
                    initial_force_field=input_force_field,
                    keep_files=settings.BEFLOW_KEEP_FILES,
                    root_directory=f"stage_{i}",
                )

            stage_results.append(result)

            if result.status != "success":
                break

            input_force_field = ForceField(
                ForceField(
                    result.refit_force_field, allow_cosmetic_attributes=True
                ).to_string(discard_cosmetic_attributes=True)
            )
        if settings.BEFLOW_KEEP_FILES:
            os.makedirs(os.path.join(home, input_schema.id), exist_ok=True)
            shutil.move(os.getcwd(), os.path.join(home, input_schema.id))

    result = BespokeOptimizationResults(input_schema=input_schema, stages=stage_results)
    # cache the final parameters
    cache_parameters(results_schema=result, redis_connection=redis_connection)

    return serialize(
        result,
        encoding="json",
    )
