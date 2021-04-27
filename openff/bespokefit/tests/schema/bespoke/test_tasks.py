"""
Test all parts of the fitting schema.
"""
import os

import pytest
from openff.qcsubmit.common_structures import MoleculeAttributes
from openff.toolkit.topology import Molecule
from simtk import unit

from openff.bespokefit.exceptions import DihedralSelectionError, MoleculeMissMatchError
from openff.bespokefit.schema.bespoke.tasks import (
    HessianTask,
    OptimizationTask,
    TorsionTask,
)
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.targets import AbInitioTargetSchema
from openff.bespokefit.utilities import get_data_file_path, get_molecule_cmiles
from openff.bespokefit.workflows.bespoke import BespokeWorkflowFactory


@pytest.fixture()
def ethane() -> Molecule:

    ethane = Molecule.from_file(
        file_path=get_data_file_path(os.path.join("test", "molecules", "ethane.sdf")),
        file_format="sdf",
    )

    return ethane


@pytest.fixture()
def occo() -> Molecule:

    occo = Molecule.from_file(
        file_path=get_data_file_path(os.path.join("test", "molecules", "OCCO.sdf")),
        file_format="sdf",
    )

    return occo


@pytest.fixture()
def ethane_opt_task(ethane) -> OptimizationTask:
    """
    Return the ethane fitting entry.
    """

    attributes = get_molecule_cmiles(molecule=ethane)

    entry = OptimizationTask(
        name="test",
        fragment=False,
        input_conformers=[
            conformer.in_units_of(unit.angstrom) for conformer in ethane.conformers
        ],
        attributes=attributes,
    )

    return entry


def get_fitting_schema(molecule: Molecule) -> BespokeOptimizationSchema:
    """
    Make a fitting schema for testing from the input molecules.
    """
    workflow_factory = BespokeWorkflowFactory(
        optimizer=ForceBalanceSchema(), target_templates=[AbInitioTargetSchema()]
    )

    schema = workflow_factory.optimization_schema_from_molecule(molecule=molecule)
    return schema


@pytest.mark.parametrize(
    "fitting_task",
    [
        pytest.param(TorsionTask, id="Torsion task"),
        pytest.param(OptimizationTask, id="Optimization task"),
        pytest.param(HessianTask, id="Hessian task"),
    ],
)
def test_making_a_fitting_task(ethane, fitting_task):
    """
    Try and a make a fitting task of each type for ethane.
    """

    attributes = get_molecule_cmiles(molecule=ethane)

    task = fitting_task(
        input_conformers=[ethane.conformers[0].value_in_unit(unit.angstrom)],
        name="test",
        attributes=attributes,
        fragment=False,
        dihedrals=[(2, 0, 1, 5)],
    )

    # now try and make a hash and qcsubmit task
    _ = task.get_task_hash()
    _ = task.get_qcsubmit_task()
    assert task.initial_molecule.n_conformers == 1
    assert task.graph_molecule == ethane
    # make sure there is no reference data
    assert task.collected is False


def test_fitting_entry_conformer_reshape(ethane, ethane_opt_task):
    """
    Make sure any flat conformers passed to the data are reshaped this is manly used when reading from json.
    """

    # now try and add input conformers correctly
    ethane_opt_task.input_conformers = [
        ethane.conformers[0],
    ]
    assert ethane_opt_task.input_conformers[0].shape == (8, 3)
    # now reset the conformers
    ethane_opt_task.input_conformers = []
    # now add a flat array
    ethane_opt_task.input_conformers = [
        ethane.conformers[0].flatten().tolist(),
    ]
    assert ethane_opt_task.input_conformers[0].shape == (8, 3)


def test_ready_for_fitting(qc_torsion_drive_record):
    """
    Make sure that a fitting entry knows when it is ready for fitting.
    """

    record, molecule = qc_torsion_drive_record

    task = TorsionTask(
        name="mol",
        fragment=False,
        input_conformers=[molecule.conformers[0].value_in_unit(unit.angstrom)],
        attributes=MoleculeAttributes.from_openff_molecule(molecule),
        dihedrals=record.keywords.dihedrals,
    )
    assert task.collected is False

    task.update_with_results(record, molecule)
    assert task.collected is True


def test_entry_ref_data(ethane_opt_task):
    """
    Make sure the entry knows that it does not have any reference data.
    """
    # check for reference data
    assert ethane_opt_task.reference_data is None
    assert ethane_opt_task.collected is False


def test_fitting_entry_equal(ethane, ethane_opt_task):
    """
    Make sure the fitting entry __eq__ works.
    The entry should only have the same hash if the current task is the same.
    """
    # now make a hessian task, this have the same hash as we first need an optimization
    hess_task = HessianTask(
        attributes=ethane_opt_task.attributes,
        input_conformers=[ethane.conformers[0].value_in_unit(unit.angstrom)],
        fragment=False,
        name="test2",
    )
    assert ethane_opt_task == hess_task


def test_fitting_entry_not_equal(ethane, ethane_opt_task):
    """
    Make sure that two different tasks are not equal.
    """
    # now make an torsion task
    tor_task = TorsionTask(
        attributes=ethane_opt_task.attributes,
        input_conformers=[ethane.conformers[0].value_in_unit(unit.angstrom)],
        fragment=False,
        name="test3",
        dihedrals=[
            (2, 0, 1, 5),
        ],
    )
    assert ethane_opt_task != tor_task


def test_update_results_wrong_molecule(ethane, qc_torsion_drive_record):
    """
    Make sure results are rejected when the type is wrong.
    """

    task = TorsionTask(
        name="mol",
        fragment=False,
        input_conformers=[ethane.conformers[0].value_in_unit(unit.angstrom)],
        attributes=MoleculeAttributes.from_openff_molecule(ethane),
        dihedrals=[(0, 1, 2, 3)],
    )

    with pytest.raises(MoleculeMissMatchError):
        task.update_with_results(*qc_torsion_drive_record)


def test_update_results_wrong_result(qc_torsion_drive_record):
    """
    Make sure results for one molecule are not applied to another.
    """

    record, molecule = qc_torsion_drive_record

    task = TorsionTask(
        name="mol",
        fragment=False,
        input_conformers=[molecule.conformers[0].value_in_unit(unit.angstrom)],
        attributes=MoleculeAttributes.from_openff_molecule(molecule),
        dihedrals=[tuple(i + 1 for i in record.keywords.dihedrals[0])],
    )

    with pytest.raises(DihedralSelectionError):
        task.update_with_results(*qc_torsion_drive_record)
