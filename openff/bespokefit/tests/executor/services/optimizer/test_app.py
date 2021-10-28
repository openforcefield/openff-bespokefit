from celery.result import AsyncResult
from openff.fragmenter.fragment import WBOFragmenter

from openff.bespokefit.executor.services.optimizer import worker
from openff.bespokefit.executor.services.optimizer.models import (
    OptimizerGETResponse,
    OptimizerPOSTBody,
    OptimizerPOSTResponse,
)
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults
from openff.bespokefit.tests.executor.mocking.celery import mock_celery_task


def test_get_optimize(optimizer_client, redis_connection, monkeypatch):

    mock_optimization_result = BespokeOptimizationResults(
        provenance={}, status="running"
    )

    monkeypatch.setattr(
        AsyncResult,
        "_get_task_meta",
        lambda self: {"status": "SUCCESS", "result": mock_optimization_result.json()},
    )

    request = optimizer_client.get("/optimizations/1")
    request.raise_for_status()

    result = OptimizerGETResponse.parse_raw(request.text)

    assert result.status == "success"
    assert result.result is not None
    assert result.id == "1"
    assert result.self == "/api/v1/optimizations/1"

    assert result.result.status == mock_optimization_result.status
    assert result.result.provenance == mock_optimization_result.provenance


def test_post_optimize(optimizer_client, redis_connection, monkeypatch):

    submitted_task_kwargs = mock_celery_task(worker, "optimize", monkeypatch)

    input_schema = BespokeOptimizationSchema(
        smiles="CC",
        initial_force_field="openff-2.0.0.offxml",
        parameters=[],
        parameter_hyperparameters=[],
        fragmentation_engine=WBOFragmenter(),
        targets=[],
        optimizer=ForceBalanceSchema(max_iterations=1),
        target_torsion_smirks=[],
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
