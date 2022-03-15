import pytest
from qcengine.config import TaskConfig

from openff.bespokefit.executor.services.qcgenerator.qcengine import (
    TorsionDriveProcedureParallel,
    _divide_config,
)


def test_divide_config():

    task_config = TaskConfig(ncores=5, nnodes=1, memory=7, retries=1)
    divided_config = _divide_config(task_config, 2)

    assert divided_config.ncores == 2
    assert divided_config.memory == 3
    assert divided_config.nnodes == 1


class TestTorsionDriveProcedureParallel:
    @pytest.mark.parametrize(
        "task_config",
        [
            TaskConfig(ncores=1, nnodes=1, memory=5, retries=1),
            TaskConfig(ncores=2, nnodes=1, memory=5, retries=1),
        ],
    )
    def test_spawn_optimizations(self, task_config, monkeypatch):
        def mock_spawn_optimization(*args):
            return args[2][0]

        monkeypatch.setattr(
            TorsionDriveProcedureParallel,
            "_spawn_optimization",
            mock_spawn_optimization,
        )

        procedure = TorsionDriveProcedureParallel()

        results = procedure._spawn_optimizations(
            {"(0,)": [[0], [1]], "(1,)": [[2], [3]]}, None, task_config
        )

        assert results == {"(0,)": [0, 1], "(1,)": [2, 3]}
