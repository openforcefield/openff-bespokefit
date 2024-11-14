from celery.result import AsyncResult
from openff.fragmenter.fragment import WBOFragmenter

from openff.bespokefit._tests.executor.mocking.celery import mock_celery_task
from openff.bespokefit.executor.services.optimizer import worker
from openff.bespokefit.executor.services.optimizer.models import (
    OptimizerGETResponse,
    OptimizerPOSTBody,
    OptimizerPOSTResponse,
)
from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationStageSchema,
)
from openff.bespokefit.schema.optimizers import ForceBalanceSchema


def test_get_optimize(
    bespoke_optimization_results, optimizer_client, redis_connection, monkeypatch
):
    monkeypatch.setattr(
        AsyncResult,
        "_get_task_meta",
        lambda self: {
            "status": "SUCCESS",
            "result": bespoke_optimization_results.json(),
        },
    )

    request = optimizer_client.get("/optimizations/1")
    request.raise_for_status()

    result = OptimizerGETResponse.parse_raw(request.text)

    assert result.status == "success"
    assert result.result is not None
    assert result.id == "1"
    assert result.self == "/api/v1/optimizations/1"

    assert result.result.status == bespoke_optimization_results.status
    assert (
        result.result.stages[0].provenance
        == bespoke_optimization_results.stages[0].provenance
    )


def test_post_optimize(optimizer_client, redis_connection, monkeypatch):
    submitted_task_kwargs = mock_celery_task(worker, "optimize", monkeypatch)

    input_schema = BespokeOptimizationSchema(
        smiles="CC",
        initial_force_field="openff-2.2.0.offxml",
        initial_force_field_hash="test_hash",
        target_torsion_smirks=[],
        stages=[
            OptimizationStageSchema(
                parameters=[],
                parameter_hyperparameters=[],
                targets=[],
                optimizer=ForceBalanceSchema(max_iterations=1),
            )
        ],
        fragmentation_engine=WBOFragmenter(),
    )

    request = optimizer_client.post(
        "/optimizations", data=OptimizerPOSTBody(input_schema=input_schema).json()
    )
    request.raise_for_status()

    assert submitted_task_kwargs is not None

    assert submitted_task_kwargs["optimization_input_json"] == input_schema.json()

    result = OptimizerPOSTResponse.parse_raw(request.text)
    assert result.id == "1"
    assert result.self == "/api/v1/optimizations/1"
