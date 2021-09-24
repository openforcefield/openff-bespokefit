from typing import List, Optional

import pytest

from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETResponse,
    CoordinatorGETStageStatus,
    CoordinatorTask,
)
from openff.bespokefit.executor.services.coordinator.stages import (
    FragmentationStage,
    OptimizationStage,
    QCGenerationStage,
    StageType,
)
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults


def mock_task(
    pending_stages: List[StageType],
    running_stage: Optional[StageType],
    completed_stages: List[StageType],
) -> CoordinatorTask:

    return CoordinatorTask(
        id="mock-task-id",
        input_schema=BespokeOptimizationSchema(
            smiles="C",
            initial_force_field="openff-1.0.0.offxml",
            parameters=[],
            parameter_hyperparameters=[],
            optimizer=ForceBalanceSchema(),
        ),
        pending_stages=pending_stages,
        running_stage=running_stage,
        completed_stages=completed_stages,
    )


@pytest.mark.parametrize(
    "stage, expected",
    [
        (
            FragmentationStage(status="waiting"),
            CoordinatorGETStageStatus(
                stage_type="fragmentation",
                stage_status="waiting",
                stage_error=None,
                stage_ids=None,
            ),
        ),
        (
            FragmentationStage(status="success", id="123"),
            CoordinatorGETStageStatus(
                stage_type="fragmentation",
                stage_status="success",
                stage_error=None,
                stage_ids=["123"],
            ),
        ),
        (
            QCGenerationStage(
                status="errored",
                ids={0: ["321"], 1: ["123", "321"]},
                error="mock-stage-error",
            ),
            CoordinatorGETStageStatus(
                stage_type="qc-generation",
                stage_status="errored",
                stage_error="mock-stage-error",
                stage_ids=["123", "321"],
            ),
        ),
    ],
)
def test_get_status_from_stage(stage, expected):

    actual = CoordinatorGETStageStatus.from_stage(stage)

    assert actual.stage_type == expected.stage_type
    assert actual.stage_status == expected.stage_status
    assert actual.stage_error == expected.stage_error

    if expected.stage_ids is None:
        assert actual.stage_ids is None
    else:
        assert sorted(actual.stage_ids) == expected.stage_ids


@pytest.mark.parametrize(
    "task, expected",
    [
        (
            mock_task(pending_stages, running_stage, completed_stages),
            CoordinatorGETResponse(
                optimization_id="mock-task-id", smiles="C", stages=[], results=results
            ),
        )
        for pending_stages, running_stage, completed_stages, results in [
            (
                [FragmentationStage(status="waiting")],
                QCGenerationStage(status="running"),
                [
                    OptimizationStage(
                        status="success", result=BespokeOptimizationResults()
                    )
                ],
                BespokeOptimizationResults(),
            ),
            (
                [
                    FragmentationStage(status="waiting"),
                    QCGenerationStage(status="waiting"),
                ],
                None,
                [
                    OptimizationStage(
                        status="success", result=BespokeOptimizationResults()
                    )
                ],
                BespokeOptimizationResults(),
            ),
            (
                [
                    FragmentationStage(status="waiting"),
                    QCGenerationStage(status="waiting"),
                    OptimizationStage(status="waiting"),
                ],
                None,
                [],
                None,
            ),
        ]
    ],
)
def test_get_from_task(task, expected):

    actual = CoordinatorGETResponse.from_task(task)

    assert actual.optimization_id == expected.optimization_id
    assert actual.smiles == expected.smiles

    assert len(actual.stages) == 3
    assert {stage.stage_type for stage in actual.stages} == {
        "fragmentation",
        "qc-generation",
        "optimization",
    }

    assert (actual.results is None) == (True if expected.results is None else False)


@pytest.mark.parametrize(
    "task, expected_status",
    [
        (mock_task([FragmentationStage()], None, []), "waiting"),
        (mock_task([], FragmentationStage(status="running"), []), "running"),
        (mock_task([], None, [FragmentationStage(status="success")]), "success"),
        (mock_task([], None, [FragmentationStage(status="errored")]), "errored"),
        (
            mock_task(
                [QCGenerationStage(status="waiting")],
                None,
                [FragmentationStage(status="success")],
            ),
            "running",
        ),
    ],
)
def test_task_status(task, expected_status):
    assert task.status == expected_status
