import pytest
from openff.qcsubmit.common_structures import MoleculeAttributes
from openff.qcsubmit.datasets import TorsiondriveDataset, TorsionDriveEntry
from openff.toolkit.topology import Molecule
from simtk import unit

from openff.bespokefit.exceptions import DihedralSelectionError, MoleculeMissMatchError
from openff.bespokefit.schema.bespoke.tasks import (
    OptimizationTask,
    TorsionTask,
    TorsionTaskReferenceData,
)
from openff.bespokefit.schema.data import BespokeQCData
from openff.bespokefit.tests import does_not_raise


def test_bespoke_data_tasks_validator(ethane_torsion_task):

    ethane_torsion_task.name = "fake-name"

    bespoke_data = BespokeQCData(tasks=[ethane_torsion_task])

    assert len(bespoke_data.tasks) == 1
    assert bespoke_data.tasks[0].name == "torsion1d-0"


def test_bespoke_data_ready_for_fit(ethane_torsion_task, qc_torsion_drive_record):

    assert not BespokeQCData(tasks=[ethane_torsion_task]).ready_for_fitting

    ethane_torsion_task.reference_data = TorsionTaskReferenceData(
        cmiles=qc_torsion_drive_record[1].to_smiles(mapped=True),
        record=qc_torsion_drive_record[0],
        conformers={},
    )

    assert BespokeQCData(tasks=[ethane_torsion_task]).ready_for_fitting


def test_get_qcsubmit_tasks(ethane_bespoke_data):

    qc_tasks = ethane_bespoke_data.get_qcsubmit_tasks()

    assert len(qc_tasks) == 1
    assert isinstance(qc_tasks[0], TorsionDriveEntry)


def test_build_qcsubmit_dataset(ethane_torsion_task):

    bespoke_data = BespokeQCData()
    assert bespoke_data.build_qcsubmit_dataset() is None

    bespoke_data.tasks = [ethane_torsion_task]

    qc_data_set = bespoke_data.build_qcsubmit_dataset()
    assert isinstance(qc_data_set, TorsiondriveDataset)

    assert qc_data_set.n_records == 1


@pytest.mark.parametrize(
    "task_molecule, task_dihedral, expected_raises",
    [
        (None, None, does_not_raise()),
        (Molecule.from_smiles("CC"), None, pytest.raises(MoleculeMissMatchError)),
        (None, [(1, 2, 3, 4)], pytest.raises(DihedralSelectionError)),
    ],
)
def test_torsion_update_with_results(
    task_molecule, task_dihedral, expected_raises, qc_torsion_drive_record
):

    record, molecule = qc_torsion_drive_record

    task_molecule = task_molecule if task_molecule is not None else molecule
    task_dihedral = (
        task_dihedral if task_dihedral is not None else record.keywords.dihedrals
    )

    if task_molecule.n_conformers == 0:
        task_molecule.generate_conformers(n_conformers=1)

    task = TorsionTask(
        name="occo",
        fragment=False,
        input_conformers=[task_molecule.conformers[0].value_in_unit(unit.angstrom)],
        attributes=MoleculeAttributes.from_openff_molecule(task_molecule),
        dihedrals=task_dihedral,
    )

    with expected_raises:
        task.update_with_results(record, molecule)

        assert task.reference_data is not None
        assert task.reference_data.record == record


@pytest.mark.parametrize(
    "task_molecule, expected_raises",
    [
        (None, does_not_raise()),
        (Molecule.from_smiles("CC"), pytest.raises(MoleculeMissMatchError)),
    ],
)
def test_optimization_update_with_results(
    task_molecule, expected_raises, qc_optimization_record
):

    record, molecule = qc_optimization_record

    task_molecule = task_molecule if task_molecule is not None else molecule

    if task_molecule.n_conformers == 0:
        task_molecule.generate_conformers(n_conformers=1)

    task = OptimizationTask(
        name="occo",
        fragment=False,
        input_conformers=[task_molecule.conformers[0].value_in_unit(unit.angstrom)],
        attributes=MoleculeAttributes.from_openff_molecule(task_molecule),
    )

    with expected_raises:
        task.update_with_results(record, molecule)

        assert task.reference_data is not None
        assert task.reference_data.record == record


def test_get_task_map(ethane_bespoke_data):

    task_map = ethane_bespoke_data.get_task_map()
    assert len(task_map) == 1
