"""
Test all parts of the fitting schema.
"""
import os

import pytest
from openff.qcsubmit.results import TorsionDriveCollectionResult
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
        molecule=ethane,
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


def test_ready_for_fitting(ethane, ethane_opt_task):
    """
    Make sure that a fitting entry knows when it is ready for fitting.
    """
    assert ethane_opt_task.collected is False
    # now set some dummy data
    ethane_opt_task.optimization_data = {"molecule": ethane.to_qcschema(), "id": 1}
    assert ethane_opt_task.collected is True


def test_entry_ref_data(ethane_opt_task):
    """
    Make sure the entry knows that it does not have any reference data.
    """
    # check for reference data
    assert ethane_opt_task.reference_data() is None
    assert ethane_opt_task.collected is False


def test_fitting_entry_equal(ethane, ethane_opt_task):
    """
    Make sure the fitting entry __eq__ works.
    The entry should only have the same hash if the current task is the same.
    """
    # now make a hessian task, this have the same hash as we first need an optimization
    hess_task = HessianTask(
        molecule=ethane,
        attributes=ethane_opt_task.attributes,
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
        molecule=ethane,
        attributes=ethane_opt_task.attributes,
        fragment=False,
        name="test3",
        dihedrals=[
            (2, 0, 1, 5),
        ],
    )
    assert ethane_opt_task != tor_task


def test_update_results_wrong_molecule(occo):
    """
    Make sure results are rejected when the type is wrong.
    """
    # make a new molecule entry
    attributes = get_molecule_cmiles(occo)
    entry = TorsionTask(
        name="occo",
        molecule=occo,
        fragment=False,
        attributes=attributes,
        dihedrals=[(9, 3, 2, 1)],
    )

    # load up the ethane result
    result = TorsionDriveCollectionResult.parse_file(
        get_data_file_path(
            os.path.join("test", "qc-datasets", "biphenyl", "biphenyl.json.xz")
        )
    )

    with pytest.raises(MoleculeMissMatchError):
        entry.update_with_results(results=list(result.collection.values())[0])


def test_update_results_wrong_result(occo):
    """
    Make sure results for one molecule are not applied to another.
    """
    # make a new molecule entry

    attributes = get_molecule_cmiles(occo)
    entry = TorsionTask(
        name="occo",
        molecule=occo,
        attributes=attributes,
        fragment=False,
        dihedrals=[(9, 3, 2, 1)],
    )

    # load up the ethane result
    result = TorsionDriveCollectionResult.parse_file(
        get_data_file_path(os.path.join("test", "qc-datasets", "occo", "occo.json"))
    )

    # now supply the correct data but wrong molecule
    with pytest.raises(DihedralSelectionError):
        entry.update_with_results(results=list(result.collection.values())[0])


def test_update_molecule_remapping(occo):
    """
    Make sure that results are remapped when needed.
    """
    # make a new molecule entry
    attributes = get_molecule_cmiles(occo)
    entry = TorsionTask(
        name="occo",
        attributes=attributes,
        fragment=False,
        molecule=occo,
        dihedrals=[(0, 1, 2, 3)],
    )

    result = TorsionDriveCollectionResult.parse_file(
        get_data_file_path(os.path.join("test", "qc-datasets", "occo", "occo.json"))
    )

    # update the result wih no remapping
    entry.update_with_results(
        results=result.collection["[h][c:2]([h])([c:3]([h])([h])[o:4][h])[o:1][h]"]
    )

    # no remapping is done here
    # make sure the gradients are correctly applied back
    normal_gradients = entry.reference_data()[0].gradient

    # now get the molecule again in the wrong order
    can_occo = Molecule.from_file(
        file_path=get_data_file_path(
            os.path.join("test", "qc-datasets", "occo", "occo.sdf")
        ),
        file_format="sdf",
    )
    can_attributes = get_molecule_cmiles(molecule=can_occo)
    can_entry = TorsionTask(
        name="can_occo",
        fragment=False,
        molecule=can_occo,
        attributes=can_attributes,
        dihedrals=[(2, 0, 1, 3)],
    )
    # update with results that need to be remapped
    can_entry.update_with_results(
        results=result.collection["[h][c:2]([h])([c:3]([h])([h])[o:4][h])[o:1][h]"]
    )

    mapped_gradients = can_entry.reference_data()[0].gradient

    # now make sure they match
    _, atom_map = Molecule.are_isomorphic(can_occo, occo, return_atom_map=True)
    for i in range(len(normal_gradients)):
        assert normal_gradients[i].tolist() == mapped_gradients[atom_map[i]].tolist()


def test_update_task_results():
    """
    Make sure the fitting schema can correctly apply any results to the correct tasks.
    """
    biphenyl = Molecule.from_file(
        get_data_file_path(
            os.path.join("test", "qc-datasets", "biphenyl", "biphenyl.sdf"),
        ),
        "sdf",
    )

    schema = get_fitting_schema(biphenyl)
    assert schema.n_tasks == 1

    results = TorsionDriveCollectionResult.parse_file(
        get_data_file_path(
            os.path.join("test", "qc-datasets", "biphenyl", "biphenyl.json.xz")
        )
    )

    schema.update_with_results(results=results)
    # now make sure there are no tasks left
    assert schema.targets[0].reference_data.ready_for_fitting


def test_update_results_wrong_spec(occo):
    """
    Make sure that if we try to update with results computed with the wrong spec we raise an error.
    """

    schema = get_fitting_schema(occo)

    results = TorsionDriveCollectionResult.parse_file(
        get_data_file_path(os.path.join("test", "qc-datasets", "occo", "occo.json"))
    )

    with pytest.raises(Exception):
        schema.update_with_results(results=results)
