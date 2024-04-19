import pytest
from openff.fragmenter.fragment import WBOFragmenter

from openff.bespokefit.executor.services.coordinator.stages import (
    FragmentationStage,
    QCGenerationStage,
)
from openff.bespokefit.executor.services.coordinator.storage import (
    create_task,
    get_task,
)
from openff.bespokefit.executor.services.coordinator.worker import _process_task
from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationStageSchema,
)
from openff.bespokefit.schema.optimizers import ForceBalanceSchema


async def mock_enter(self, task):
    self.status = "running"


async def mock_update_success(self):
    assert self.status == "running"
    self.status = "success"


async def mock_update_errored(self):
    assert self.status == "running"
    self.status = "errored"


@pytest.mark.asyncio
async def test_process_task(redis_connection, monkeypatch):
    monkeypatch.setattr(FragmentationStage, "enter", mock_enter)
    monkeypatch.setattr(QCGenerationStage, "enter", mock_enter)

    monkeypatch.setattr(FragmentationStage, "update", mock_update_success)
    monkeypatch.setattr(QCGenerationStage, "update", mock_update_errored)

    create_task(
        input_schema=BespokeOptimizationSchema(
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
        ),
        stages=[FragmentationStage(), QCGenerationStage()],
    )

    await _process_task(1)
    task = get_task(1)

    assert len(task.pending_stages) == 1
    assert isinstance(task.pending_stages[0], QCGenerationStage)

    assert len(task.completed_stages) == 1
    assert isinstance(task.completed_stages[0], FragmentationStage)

    assert task.running_stage is None

    assert task.status == "running"

    await _process_task(1)
    task = get_task(1)

    assert len(task.pending_stages) == 0

    assert len(task.completed_stages) == 2
    assert isinstance(task.completed_stages[0], FragmentationStage)
    assert isinstance(task.completed_stages[1], QCGenerationStage)

    assert task.running_stage is None

    assert task.status == "errored"

    await _process_task(1)
