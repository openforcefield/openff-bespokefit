import pytest
from qcelemental.models.common_models import Model

from openff.bespokefit.executor.services.qcgenerator import worker
from openff.bespokefit.executor.services.qcgenerator.cache import (
    _canonicalize_task,
    cached_compute_task,
)
from openff.bespokefit.schema.tasks import (
    HessianTask,
    OptimizationSpec,
    OptimizationTask,
    Torsion1DTask,
)
from openff.bespokefit.tests.executor.mocking.celery import mock_celery_task


def test_canonicalize_torsion_task():

    original_task = Torsion1DTask(
        smiles="[H:1][C:2]([H:3])([H:4])[O:5][H:6]",
        central_bond=(2, 5),
        optimization_spec=OptimizationSpec(
            program="rdkit",
            model=Model(method="uff", basis=None),
        ),
    )
    canonical_task = _canonicalize_task(original_task)

    assert canonical_task.smiles == "[H][C:1]([H])([H])[O:2][H]"
    assert canonical_task.central_bond == (1, 2)


@pytest.mark.parametrize(
    "task, compute_function",
    [
        (
            Torsion1DTask(
                smiles="[CH2:1][CH2:2]",
                central_bond=(1, 2),
                optimization_spec=OptimizationSpec(
                    program="rdkit",
                    model=Model(method="uff", basis=None),
                ),
            ),
            "compute_torsion_drive",
        ),
        (
            OptimizationTask(
                smiles="[CH2:1][CH2:2]",
                n_conformers=1,
                optimization_spec=OptimizationSpec(
                    program="rdkit",
                    model=Model(method="uff", basis=None),
                ),
            ),
            "compute_optimization",
        ),
        (
            HessianTask(
                smiles="[CH2:1][CH2:2]",
                optimization_spec=OptimizationSpec(
                    program="rdkit",
                    model=Model(method="uff", basis=None),
                ),
            ),
            "compute_hessian",
        ),
    ],
)
def test_cached_compute_task(
    qcgenerator_client, redis_connection, monkeypatch, task, compute_function
):

    mock_celery_task(worker, compute_function, monkeypatch, "task-1")

    task_id = cached_compute_task(task, redis_connection)
    assert redis_connection.hget("qcgenerator:types", "task-1").decode() == task.type

    mock_celery_task(worker, compute_function, monkeypatch, "task-2")

    assert cached_compute_task(task, redis_connection) == task_id
