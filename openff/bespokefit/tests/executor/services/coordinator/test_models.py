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
from openff.bespokefit.executor.services.models import Link
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
            target_torsion_smirks=[],
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
                type="fragmentation",
                status="waiting",
                error=None,
                results=None,
            ),
        ),
        (
            FragmentationStage(status="success", id="123"),
            CoordinatorGETStageStatus(
                type="fragmentation",
                status="success",
                error=None,
                results=[Link(id="123", self="/api/v1/fragmentations/123")],
            ),
        ),
        (
            QCGenerationStage(
                status="errored",
                ids={0: ["321"], 1: ["123", "321"]},
                error="mock-stage-error",
            ),
            CoordinatorGETStageStatus(
                type="qc-generation",
                status="errored",
                error="mock-stage-error",
                results=[
                    Link(id="123", self="/api/v1/qc-calcs/123"),
                    Link(id="321", self="/api/v1/qc-calcs/321"),
                ],
            ),
        ),
    ],
)
def test_get_status_from_stage(stage, expected):

    actual = CoordinatorGETStageStatus.from_stage(stage)

    assert actual.type == expected.type
    assert actual.status == expected.status
    assert actual.error == expected.error

    if expected.results is None:
        assert actual.results is None
    else:
        assert sorted(actual.results) == expected.results


@pytest.mark.parametrize(
    "task, expected",
    [
        (
            mock_task(pending_stages, running_stage, completed_stages),
            CoordinatorGETResponse(
                id="mock-task-id",
                self="",
                stages=[],
                results=results,
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

    assert actual.id == expected.id

    assert len(actual.stages) == 3
    assert {stage.type for stage in actual.stages} == {
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
