import json

import pytest
from openff.toolkit.topology import Molecule
from qcelemental.models.common_models import Model
from qcelemental.models.procedures import OptimizationResult, TorsionDriveResult

from openff.bespokefit.executor.services.qcgenerator import worker
from openff.bespokefit.schema.tasks import OptimizationTask, Torsion1DTask


def test_compute_torsion_drive():

    task = Torsion1DTask(
        smiles="[CH3:1][CH3:2]",
        central_bond=(1, 2),
        grid_spacing=180,
        scan_range=(-180, 180),
        program="rdkit",
        model=Model(method="uff", basis=None),
    )

    result_json = worker.compute_torsion_drive(task.json())
    assert isinstance(result_json, str)

    result_dict = json.loads(result_json)
    assert isinstance(result_dict, dict)

    result = TorsionDriveResult.parse_obj(result_dict)
    assert result.success

    cmiles = result.final_molecules["180"].extras[
        "canonical_isomeric_explicit_hydrogen_mapped_smiles"
    ]

    # Make sure a molecule can be created from CMILES
    final_molecule = Molecule.from_mapped_smiles(cmiles)
    assert Molecule.are_isomorphic(final_molecule, Molecule.from_smiles("CC"))[0]


def test_compute_optimization():

    task = OptimizationTask(
        smiles="CCCCC",
        n_conformers=2,
        program="rdkit",
        model=Model(method="uff", basis=None),
    )

    result_json = worker.compute_optimization(task.json())
    assert isinstance(result_json, str)

    result_dicts = json.loads(result_json)

    assert isinstance(result_dicts, list)
    assert 0 < len(result_dicts) <= 2

    for result_dict in result_dicts:

        result = OptimizationResult.parse_obj(result_dict)
        assert result.success

        cmiles = result.final_molecule.extras[
            "canonical_isomeric_explicit_hydrogen_mapped_smiles"
        ]

        # Make sure a molecule can be created from CMILES
        final_molecule = Molecule.from_mapped_smiles(cmiles)
        assert Molecule.are_isomorphic(final_molecule, Molecule.from_smiles("CCCCC"))


@pytest.mark.parametrize(
    "compute_function, task",
    [
        (
            worker.compute_torsion_drive,
            Torsion1DTask(
                smiles="[CH2:1]=[CH2:2]",
                central_bond=(1, 2),
                grid_spacing=180,
                scan_range=(-180, 180),
                program="non-existent-program",
                model=Model(method="uff", basis=None),
            ),
        ),
        (
            worker.compute_optimization,
            OptimizationTask(
                smiles="CCCCC",
                n_conformers=1,
                program="non-existent-program",
                model=Model(method="uff", basis=None),
            ),
        ),
    ],
)
def test_compute_failure(compute_function, task, celery_worker):

    with pytest.raises(ValueError, match="non-existent-program"):
        compute_function(task.json())
