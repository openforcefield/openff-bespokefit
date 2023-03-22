import os
import shutil
from typing import Union

from pydantic import parse_raw_as
from qcelemental.util import serialize

from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.services.coordinator.utils import cache_parameters
from openff.bespokefit.executor.utilities.celery import configure_celery_app
from openff.bespokefit.executor.utilities.redis import (
    connect_to_default_redis,
    is_redis_available,
)
from openff.bespokefit.optimizers import get_optimizer
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.results import (
    BespokeOptimizationResults,
    OptimizationStageResults,
)
from openff.bespokefit.utilities.tempcd import temporary_cd

celery_app = configure_celery_app("optimizer", connect_to_default_redis(validate=False))


@celery_app.task(bind=True, acks_late=True)
def optimize(self, optimization_input_json: str) -> str:
    from openff.toolkit.typing.engines.smirnoff import ForceField

    settings = current_settings()

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
            # If there are no parameters to optimise as they have all been cached mock
            # the result
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
                    keep_files=settings.BEFLOW_OPTIMIZER_KEEP_FILES
                    or settings.BEFLOW_KEEP_TMP_FILES,
                    root_directory=f"stage_{i}",
                )

            stage_results.append(result)

            if result.status != "success":
                raise (
                    RuntimeError("an unknown error occurred")
                    if result.error is None
                    else RuntimeError(
                        f"{result.error.type}: "
                        f"{result.error.message}\n{result.error.traceback}"
                    )
                )

            input_force_field = ForceField(
                ForceField(
                    result.refit_force_field, allow_cosmetic_attributes=True
                ).to_string(discard_cosmetic_attributes=True)
            )

        if settings.BEFLOW_OPTIMIZER_KEEP_FILES:
            os.makedirs(os.path.join(home, input_schema.id), exist_ok=True)
            shutil.copytree(os.getcwd(), os.path.join(home, input_schema.id))

    result = BespokeOptimizationResults(input_schema=input_schema, stages=stage_results)
    # cache the final parameters
    if (
        is_redis_available(
            host=settings.BEFLOW_REDIS_ADDRESS, port=settings.BEFLOW_REDIS_PORT
        )
        and result.refit_force_field is not None
    ):
        cache_parameters(
            results_schema=result, redis_connection=connect_to_default_redis()
        )

    return serialize(
        result,
        encoding="json",
    )
