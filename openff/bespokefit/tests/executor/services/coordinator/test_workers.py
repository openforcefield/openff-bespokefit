import pickle

import pytest
from openff.fragmenter.fragment import WBOFragmenter

from openff.bespokefit.executor.services.coordinator.models import CoordinatorTask
from openff.bespokefit.executor.services.coordinator.stages import (
    FragmentationStage,
    QCGenerationStage,
)
from openff.bespokefit.executor.services.coordinator.worker import _cycle
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
async def test_internal_cycle(redis_connection, monkeypatch):

    task_key = "coordinator:optimization:1"

    monkeypatch.setattr(FragmentationStage, "enter", mock_enter)
    monkeypatch.setattr(QCGenerationStage, "enter", mock_enter)

    monkeypatch.setattr(FragmentationStage, "update", mock_update_success)
    monkeypatch.setattr(QCGenerationStage, "update", mock_update_errored)

    task = CoordinatorTask(
        id="1",
        input_schema=BespokeOptimizationSchema(
            smiles="CC",
            initial_force_field="openff-2.0.0.offxml",
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
        pending_stages=[FragmentationStage(), QCGenerationStage()],
    )

    redis_connection.set(task_key, pickle.dumps(task.dict()))
    redis_connection.zadd("coordinator:optimizations", {task_key: task.id})

    await _cycle()
    task = CoordinatorTask.parse_obj(pickle.loads(redis_connection.get(task_key)))

    assert len(task.pending_stages) == 1
    assert isinstance(task.pending_stages[0], QCGenerationStage)

    assert len(task.completed_stages) == 1
    assert isinstance(task.completed_stages[0], FragmentationStage)

    assert task.running_stage is None

    assert task.status == "running"

    await _cycle()
    task = CoordinatorTask.parse_obj(pickle.loads(redis_connection.get(task_key)))

    assert len(task.pending_stages) == 0

    assert len(task.completed_stages) == 2
    assert isinstance(task.completed_stages[0], FragmentationStage)
    assert isinstance(task.completed_stages[1], QCGenerationStage)

    assert task.running_stage is None

    assert task.status == "errored"

    await _cycle()
