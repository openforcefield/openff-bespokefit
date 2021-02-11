"""
Test all parts of the fitting schema.
"""

from typing import List, Tuple

import pytest
from openforcefield.topology import Molecule

from openff.bespokefit.exceptions import (
    DihedralSelectionError,
    MoleculeMissMatchError,
    OptimizerError,
)
from openff.bespokefit.optimizers import (
    ForceBalanceOptimizer,
    deregister_optimizer,
    register_optimizer,
)
from openff.bespokefit.schema import (
    FittingSchema,
    HessianTask,
    OptimizationTask,
    TorsionTask,
)
from openff.bespokefit.targets import AbInitio_SMIRNOFF
from openff.bespokefit.utils import get_data, get_molecule_cmiles
from openff.bespokefit.workflow import WorkflowFactory
from openff.qcsubmit.results import TorsionDriveCollectionResult
from openff.qcsubmit.testing import temp_directory


def ethane_opt_task() -> Tuple[OptimizationTask, Molecule]:
    """
    Return the ethane fitting entry.
    """
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    attributes = get_molecule_cmiles(molecule=ethane)
    entry = OptimizationTask(molecule=ethane, fragment=False, attributes=attributes, name="test")
    return entry, ethane


def get_fitting_schema(molecules: List[Molecule]):
    """
    Make a fitting schema for testing from the input molecules.
    """
    workflow = WorkflowFactory()
    fb = ForceBalanceOptimizer()
    fb.set_optimization_target(target=AbInitio_SMIRNOFF())
    workflow.set_optimizer(fb)
    schema = workflow.fitting_schema_from_molecules(molecules=molecules, processors=1)
    return schema


@pytest.mark.parametrize("fitting_task", [
    pytest.param(TorsionTask, id="Torsion task"),
    pytest.param(OptimizationTask, id="Optimization task"),
    pytest.param(HessianTask, id="Hessian task")
])
def test_making_a_fitting_task(fitting_task):
    """
    Try and a make a fitting task of each type for ethane.
    """
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    attributes = get_molecule_cmiles(molecule=ethane)
    task = fitting_task(molecule=ethane, name="test", attributes=attributes, fragment=False, dihedrals=[(2, 0, 1, 5)])
    # now try and make a hash and qcsubmit task
    _ = task.get_task_hash()
    _ = task.get_qcsubmit_task()
    assert task.initial_molecule.n_conformers == 1
    assert task.graph_molecule == ethane
    # make sure there is no reference data
    assert task.collected is False


def test_fitting_entry_conformer_reshape():
    """
    Make sure any flat conformers passed to the data are reshaped this is manly used when reading from json.
    """
    entry, ethane = ethane_opt_task()
    # now try and add input conformers correctly
    entry.input_conformers = [ethane.conformers[0], ]
    assert entry.input_conformers[0].shape == (8, 3)
    # now reset the conformers
    entry.input_conformers = []
    # now add a flat array
    entry.input_conformers = [ethane.conformers[0].flatten().tolist(), ]
    assert entry.input_conformers[0].shape == (8, 3)


def test_ready_for_fitting():
    """
    Make sure that a fitting entry knows when it is ready for fitting.
    """
    entry, ethane = ethane_opt_task()
    assert entry.collected is False
    # now set some dummy data
    entry.optimization_data = {"molecule": ethane.to_qcschema(), "id":1}
    assert entry.collected is True


def test_entry_ref_data():
    """
    Make sure the entry knows that it does not have any reference data.
    """
    entry, ethane = ethane_opt_task()
    # check for reference data
    assert entry.reference_data() is None
    assert entry.collected is False


def test_fitting_entry_equal():
    """
    Make sure the fitting entry __eq__ works.
    The entry should only have the same hash if the current task is the same.
    """
    entry, ethane = ethane_opt_task()
    # now make a hessian task, this have the same hash as we first need an optimization
    hess_task = HessianTask(molecule=ethane, attributes=entry.attributes, fragment=False, name="test2")
    assert entry == hess_task


def test_fitting_entry_not_equal():
    """
    Make sure that two different tasks are not equal.
    """
    entry, ethane = ethane_opt_task()
    # now make an torsion task
    tor_task = TorsionTask(molecule=ethane, attributes=entry.attributes, fragment=False, name="test3", dihedrals=[(2, 0, 1, 5), ])
    assert entry != tor_task


def test_update_results_wrong_molecule():
    """
    Make sure results are rejected when the type is wrong.
    """
    # make a new molecule entry
    occo = Molecule.from_file(file_path=get_data("OCCO.sdf"), file_format="sdf")
    attributes = get_molecule_cmiles(occo)
    entry = TorsionTask(name="occo", molecule=occo, fragment=False, attributes=attributes, dihedrals=[(9, 3, 2, 1)])
    # load up the ethane result
    result = TorsionDriveCollectionResult.parse_file(get_data("biphenyl.json.xz"))
    with pytest.raises(MoleculeMissMatchError):
        entry.update_with_results(results=list(result.collection.values())[0])


def test_update_results_wrong_result():
    """
    Make sure results for one molecule are not applied to another.
    """
    # make a new molecule entry
    occo = Molecule.from_file(file_path=get_data("OCCO.sdf"), file_format="sdf")
    attributes = get_molecule_cmiles(occo)
    entry = TorsionTask(name="occo", molecule=occo, attributes=attributes, fragment=False, dihedrals=[(9, 3, 2, 1)])
    # load up the ethane result
    result = TorsionDriveCollectionResult.parse_file(get_data("occo.json"))

    # now supply the correct data but wrong molecule
    with pytest.raises(DihedralSelectionError):
        entry.update_with_results(results=list(result.collection.values())[0])


def test_update_molecule_remapping():
    """
    Make sure that results are remapped when needed.
    """
    # make a new molecule entry
    occo = Molecule.from_file(file_path=get_data("OCCO.sdf"), file_format="sdf")
    attributes = get_molecule_cmiles(occo)
    entry = TorsionTask(name="occo", attributes=attributes, fragment=False, molecule=occo, dihedrals=[(0, 1, 2, 3)])

    result = TorsionDriveCollectionResult.parse_file(get_data("occo.json"))
    # update the result wih no remapping
    entry.update_with_results(results=result.collection["[h][c:2]([h])([c:3]([h])([h])[o:4][h])[o:1][h]"])

    # no remapping is done here
    # make sure the gradients are correctly applied back
    normal_gradients = entry.reference_data()[0].gradient

    # now get the molecule again in the wrong order
    can_occo = Molecule.from_file(file_path=get_data("can_occo.sdf"), file_format="sdf")
    can_attributes = get_molecule_cmiles(molecule=can_occo)
    can_entry = TorsionTask(name="can_occo", fragment=False, molecule=can_occo, attributes=can_attributes, dihedrals=[(2, 0, 1, 3)])
    # update with results that need to be remapped
    can_entry.update_with_results(results=result.collection["[h][c:2]([h])([c:3]([h])([h])[o:4][h])[o:1][h]"])

    mapped_gradients = can_entry.reference_data()[0].gradient

    # now make sure they match
    _, atom_map = Molecule.are_isomorphic(can_occo, occo, return_atom_map=True)
    for i in range(len(normal_gradients)):
        assert normal_gradients[i].tolist() == mapped_gradients[atom_map[i]].tolist()


def test_fitting_add_optimizer():
    """
    Test adding optimizers to the fitting schema
    """

    fitting = FittingSchema()
    fb = ForceBalanceOptimizer()
    fitting.add_optimizer(optimizer=fb)
    assert fb.optimizer_name.lower() in fitting.optimizer_settings
    # now try and add an optimizer which is missing
    fitting.optimizer_settings = {}
    deregister_optimizer(optimizer=fb)
    with pytest.raises(OptimizerError):
        fitting.add_optimizer(optimizer=fb)

    # now reset the optimizers
    register_optimizer(optimizer=fb)


def test_fitting_add_optimizer_and_targets():
    """
    If we add a valid optimizer with targets make sure all the info is saved.
    """
    fitting = FittingSchema()
    fb = ForceBalanceOptimizer()
    target = AbInitio_SMIRNOFF()
    fb.set_optimization_target(target=target)
    fitting.add_optimizer(optimizer=fb)
    assert target.name in fitting.target_settings


def test_get_optimizers():
    """
    Make sure that the optimizers in the workflow can be remade with the correct settings.
    """

    fitting = FittingSchema()
    assert [] == fitting.get_optimizers
    # now add the optimizers
    fb = ForceBalanceOptimizer(penalty_type="L1")
    fitting.add_optimizer(optimizer=fb)
    assert [fb, ] == fitting.get_optimizers


def test_get_optimizer():
    """
    Make sure that the fitting schema can correctly remake a specific optimizer.
    """
    fitting = FittingSchema()
    # try and get an optimizer
    with pytest.raises(OptimizerError):
        _ = fitting.get_optimizer(optimizer_name="forcebalanceoptimizer")

    # now add forcebalance
    fb = ForceBalanceOptimizer(penalty_type="L1")
    fitting.add_optimizer(optimizer=fb)
    assert fb == fitting.get_optimizer(optimizer_name=fb.optimizer_name)

    with pytest.raises(OptimizerError):
        _ = fitting.get_optimizer(optimizer_name="badoptimizer")


def test_fitting_export_roundtrip():
    """
    Make sure that the fitting schema can be exported and imported.
    """

    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    schema = get_fitting_schema(molecules=[ethane, ])

    with temp_directory():
        schema.export_schema(file_name="fitting.json")

        schema2 = FittingSchema.parse_obj(schema)
        assert schema.json() == schema2.json()


def test_export_schema_error():
    """
    Make sure an error is raised if we try to export to the wrong type of file.
    """
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    schema = get_fitting_schema(molecules=[ethane, ])

    with temp_directory():
        with pytest.raises(RuntimeError):
            schema.export_schema(file_name="schema.yaml")


def test_schema_tasks():
    """
    Make sure that a schema with multipule similar tasks can deduplicate tasks.
    """
    occo = Molecule.from_file(file_path=get_data("OCCO.sdf"), file_format="sdf")
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    schema = get_fitting_schema(molecules=[occo, ethane])

    assert schema.n_molecules == 2
    # occo is the only molecule which should have a torsion to target
    assert schema.n_tasks == 1


def test_update_results_fitting_schema():
    """
    Make sure the fitting schema can correctly apply any results to the correct tasks.
    """
    biphenyl = Molecule.from_file(file_path=get_data("biphenyl.sdf"), file_format="sdf")
    schema = get_fitting_schema(molecules=[biphenyl, ])
    assert schema.n_tasks == 1
    results = TorsionDriveCollectionResult.parse_file(get_data("biphenyl.json.xz"))
    schema.update_with_results(results=results)
    # now make sure there are no tasks left
    assert schema.tasks[0].ready_for_fitting is True


def test_update_results_wrong_spec():
    """
    Make sure that if we try to update with results computed with the wrong spec we raise an error.
    """
    occo = Molecule.from_file(file_path=get_data("OCCO.sdf"), file_format="sdf")
    schema = get_fitting_schema(molecules=[occo, ])
    results = TorsionDriveCollectionResult.parse_file(get_data("occo.json"))
    with pytest.raises(Exception):
        schema.update_with_results(results=results)


def test_schema_to_qcsubmit_torsiondrives():
    """
    Make a qcsubmit dataset from the fitting schema.
    """
    occo = Molecule.from_file(file_path=get_data("OCCO.sdf"), file_format="sdf")
    biphenyl = Molecule.from_file(file_path=get_data("biphenyl.sdf"), file_format="sdf")
    schema = get_fitting_schema(molecules=[occo, biphenyl])
    # make a torsiondrive dataset
    datasets = schema.generate_qcsubmit_datasets()
    assert len(datasets) == 1
    tdrive = datasets[0]
    # we should have two molecules and 2 tdrives in total
    assert tdrive.n_molecules == 2
    assert tdrive.n_records == 2
    # now add a result and run again
    result = TorsionDriveCollectionResult.parse_file(get_data("biphenyl.json.xz"))
    schema.update_with_results(results=result)
    datasets = schema.generate_qcsubmit_datasets()

    tdrive2 = datasets[0]
    assert tdrive2.n_molecules == 1
    assert tdrive2.n_records == 1


def test_fitting_schema_roundtrip():
    """
    Make sure that a full fitting schema can be exported to file and read back in.
    """
    occo = Molecule.from_file(file_path=get_data("OCCO.sdf"), file_format="sdf")
    schema = get_fitting_schema(molecules=[occo, ])
    with temp_directory():
        schema.export_schema("test.json.xz")
        schema2 = FittingSchema.parse_file("test.json.xz")
        assert schema.molecules == schema2.molecules
        assert schema.entry_molecules == schema2.entry_molecules
