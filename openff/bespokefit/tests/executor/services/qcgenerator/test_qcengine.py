import pytest
from openff.toolkit import Molecule
from qcelemental.models.common_models import DriverEnum, Model
from qcelemental.models.procedures import (
    OptimizationSpecification,
    QCInputSpecification,
    TDKeywords,
    TorsionDriveInput,
)
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

        molecule: Molecule = Molecule.from_smiles("CC")
        molecule.generate_conformers(n_conformers=1)

        input_schema = TorsionDriveInput(
            keywords=TDKeywords(dihedrals=[(0, 1, 2, 3)], grid_spacing=[15]),
            initial_molecule=[molecule.to_qcschema(conformer=0)],
            input_specification=QCInputSpecification(
                model=Model(method="hf", basis="6-31G*"),
                driver=DriverEnum.gradient,
            ),
            optimization_spec=OptimizationSpecification(
                procedure="geometric",
                keywords={"program": "geometric"},
            ),
        )

        results = procedure._spawn_optimizations(
            {"(0,)": [[0], [1]], "(1,)": [[2], [3]]}, input_schema, task_config
        )

        assert results == {"(0,)": [0, 1], "(1,)": [2, 3]}
