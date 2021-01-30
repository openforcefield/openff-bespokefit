"""
Test all parts of the fitting schema.
"""

from typing import List, Tuple

import pytest
from openforcefield.topology import Molecule

from openff.bespokefit.collection_workflows import (
    CollectionMethod,
    HessianWorkflow,
    Precedence,
    TorsiondriveWorkflow,
    WorkflowStage,
)
from openff.bespokefit.common_structures import Status
from openff.bespokefit.exceptions import (
    DihedralSelectionError,
    MissingReferenceError,
    MissingWorkflowError,
    MoleculeMissMatchError,
    OptimizerError,
)
from openff.bespokefit.optimizers import (
    ForceBalanceOptimizer,
    deregister_optimizer,
    register_optimizer,
)
from openff.bespokefit.schema import (
    AngleSmirks,
    AtomSmirks,
    FittingEntry,
    FittingSchema,
)
from openff.bespokefit.targets import AbInitio_SMIRNOFF
from openff.bespokefit.utils import get_data, get_molecule_cmiles
from openff.bespokefit.workflow import WorkflowFactory
from openff.qcsubmit.common_structures import QCSpec
from openff.qcsubmit.datasets import OptimizationDataset, TorsiondriveDataset
from openff.qcsubmit.results import TorsionDriveCollectionResult
from openff.qcsubmit.testing import temp_directory


def ethane_fitting_entry() -> Tuple[FittingEntry, Molecule]:
    """
    Return the ethane fitting entry.
    """
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    attributes = get_molecule_cmiles(molecule=ethane)
    entry = FittingEntry(name="ethane", attributes=attributes, extras={"dihedrals": (2, 0, 1, 5)})
    return entry, ethane


def test_fitting_entry_roundtrip():
    """
    Make sure that the fitting entry can round trip correctly.
    """
    entry, ethane = ethane_fitting_entry()
    tor = AngleSmirks(smirks="[#1:1]-[#6:2]-[#6:3]", atoms={(0, 1, 2)}, k=100, angle=120)
    entry.target_smirks = [tor, ]
    entry2 = FittingEntry.parse_obj(entry.dict())
    assert entry.json() == entry2.json()


def get_fitting_schema(molecules: List[Molecule]):
    """
    Make a fitting schema for testing from the input molecules.
    """
    workflow = WorkflowFactory(client="snowflake")
    fb = ForceBalanceOptimizer()
    fb.set_optimization_target(target=AbInitio_SMIRNOFF(fragmentation=False))
    workflow.set_optimizer(fb)
    schema = workflow.create_fitting_schema(molecules=molecules)
    return schema


def test_fitting_entry_conformer_reshape():
    """
    Make sure any flat conformers passed to the data are reshaped this is manly used when reading from json.
    """
    entry, ethane = ethane_fitting_entry()
    # now try and add input conformers correctly
    entry.input_conformers = [ethane.conformers[0], ]
    assert entry.input_conformers[0].shape == (8, 3)
    # now reset the conformers
    entry.input_conformers = []
    # now add a flat array
    entry.input_conformers = [ethane.conformers[0].flatten().tolist(), ]
    assert entry.input_conformers[0].shape == (8, 3)


@pytest.mark.parametrize("extras_data", [
    pytest.param(({"dihedrals": (0, 1, 2, 3)}, None), id="1D Dihedral raw"),
    pytest.param(({"dihedrals": [(0, 1, 2, 3), ]}, None), id="1D Dihedral listed"),
    pytest.param(({"dihedrals": [(0, 1, 2, 3), (1, 2, 3, 4)]}, None), id="2D Dihedral"),
    pytest.param(({"dihedrals": [(0, 1, 2, 3), (1, 2, 3, 4), (4, 5, 6, 7)]}, DihedralSelectionError), id="3D Dihedral"),
])
def test_fitting_entry_extras(extras_data):
    """
    Test adding different extras to a fitting entry.
    """
    entry, ethane = ethane_fitting_entry()
    extras, error = extras_data
    if error is None:
        entry.extras = extras
    else:
        with pytest.raises(DihedralSelectionError):
            entry.extras = extras


def test_fitting_entry_input_molecule():
    """
    Make sure the fitting entry returns the correct molecule and uses the input conformers where possible.
    """
    entry, ethane = ethane_fitting_entry()
    # test the molecules are the same
    input_mol = entry.initial_molecule
    assert input_mol.n_conformers == 0
    assert ethane == entry.initial_molecule
    # now add the input conformer
    entry.input_conformers = [ethane.conformers[0], ]
    # make the molecule again
    input_mol = entry.initial_molecule
    assert input_mol.n_conformers == 1


def test_fitting_entry_current_molecule():
    """
    Make sure the current molecule picks up any result conformers.
    """
    entry, ethane = ethane_fitting_entry()
    current_mol = entry.current_molecule
    assert ethane == current_mol
    assert current_mol.n_conformers == 0
    # update with results
    torsion_scan = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
    entry.collection_workflow = TorsiondriveWorkflow
    entry.update_with_results(results=torsion_scan.collection["[h:1][c:2]([h])([h])[c:3]([h:4])([h])[h]"])
    result_molecule = entry.current_molecule
    assert result_molecule == ethane
    # make sure the full torsiondrive conformers are found
    assert result_molecule.n_conformers == 24


def test_adding_target_smirks():
    """
    Make sure atoms are transferred when two identical smirks patterns are found for the same molecule.
    """

    entry, ethane = ethane_fitting_entry()
    entry.add_target_smirks(smirks=AtomSmirks(smirks="[#1:1]", atoms={(2,)}, epsilon=0, rmin_half=0))
    # make sure it is added
    assert len(entry.target_smirks) == 1
    assert entry.target_smirks[0].atoms - {(2,)} == set()
    # now add another
    entry.add_target_smirks(smirks=AtomSmirks(smirks="[#1:1]", atoms={(3,)}, epsilon=0, rmin_half=0))
    assert len(entry.target_smirks) == 1
    assert entry.target_smirks[0].atoms - {(2,)} == {(3,)}


def test_get_next_task():
    """
    Make sure the correct next task is returned
    """
    entry, ethane = ethane_fitting_entry()
    # make sure there are no tasks
    assert entry.current_tasks() == []
    # add a standard workflow
    entry.collection_workflow = TorsiondriveWorkflow
    assert len(entry.current_tasks()) == 1
    # now add some tasks that can be done in parallel
    entry.collection_workflow = HessianWorkflow
    assert len(entry.current_tasks()) == 1
    # now allow both the opt and hessian to be done in parallel
    entry.collection_workflow[0].precedence = Precedence.Parallel
    entry.collection_workflow[1].precedence = Precedence.Parallel
    assert len(entry.current_tasks()) == 2


def test_ready_for_fitting():
    """
    Make sure that a fitting entry knows when it is ready for fitting.
    """
    entry, ethane = ethane_fitting_entry()
    assert entry.ready_for_fitting is False
    # now add a workflow stage
    entry.collection_workflow = TorsiondriveWorkflow
    assert entry.ready_for_fitting is False
    # now set the status to true
    entry.collection_workflow[0].status = Status.Complete
    entry.collection_workflow[0].result = []
    assert entry.ready_for_fitting is True


def test_entry_ref_data():
    """
    Make sure the correct errors are raised when requesting reference data.
    """
    entry, ethane = ethane_fitting_entry()
    # check for reference data
    with pytest.raises(MissingWorkflowError):
        _ = entry.get_reference_data()
    # now add a workflow
    entry.collection_workflow = TorsiondriveWorkflow
    # check for reference again
    with pytest.raises(MissingReferenceError):
        _ = entry.get_reference_data()

    # now add some data
    results = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
    entry.update_with_results(results=results.collection["[h:1][c:2]([h])([h])[c:3]([h:4])([h])[h]"])
    data = entry.get_reference_data()
    assert len(data) == 24


def test_entry_hashing():
    """
    Make sure that the entry hashing correctly works out duplicate tasks.
    """
    entry, ethane = ethane_fitting_entry()
    # get the hash with no tasks
    general_hash = entry.get_hash()
    assert general_hash == "b6bf10678bd7f47028dcfe9083caa9c5edcae31a"
    # now add different tasks and make sure the hash is different
    entry.collection_workflow = TorsiondriveWorkflow
    torsion_hash = entry.get_hash()
    # get a multi task hash
    entry.collection_workflow = HessianWorkflow
    hessian_hash = entry.get_hash()
    assert torsion_hash != general_hash
    assert torsion_hash != hessian_hash
    opt_hash = entry.get_task_hash(stage=entry.collection_workflow[0])
    assert opt_hash != hessian_hash
    assert opt_hash != general_hash
    # now change the QCspec
    entry.qc_spec = QCSpec(method="ani1ccx", basis=None, program="torchani", spec_name="ani", spec_description="ani spec")
    # now compute the hash again
    new_hessian_hash = entry.get_hash()
    assert new_hessian_hash != hessian_hash
    # now add a local method
    entry.collection_workflow = [WorkflowStage(method=CollectionMethod.Local),]
    entry.provenance = {"target": "LocalCollector"}
    local_hash = entry.get_hash()
    assert local_hash != new_hessian_hash


def test_fitting_entry_equal():
    """
    Make sure the fitting entry __eq__ works.
    Entries are only the same if the hash is the same so the spec and collection workflow must be the same.
    """
    entry, ethane = ethane_fitting_entry()
    entry2 = entry.copy(deep=True)
    entry2.collection_workflow = TorsiondriveWorkflow
    assert entry != entry2


def test_update_results_wrong_result():
    """
    Make sure results are rejected when the type is wrong.
    """
    # make a new molecule entry
    occo = Molecule.from_file(file_path=get_data("OCCO.sdf"), file_format="sdf")
    attributes = get_molecule_cmiles(occo)
    entry = FittingEntry(name="occo", collection_workflow=TorsiondriveWorkflow, attributes=attributes, extras={"dihedrals": (9, 3, 2, 1)})
    # load up the ethane result
    result = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
    with pytest.raises(NotImplementedError):
        entry.update_with_results(results=result)


def test_update_results_wrong_molecule():
    """
    Make sure results for one molecule are not applied to another.
    """
    # make a new molecule entry
    occo = Molecule.from_file(file_path=get_data("OCCO.sdf"), file_format="sdf")
    attributes = get_molecule_cmiles(occo)
    entry = FittingEntry(name="occo", collection_workflow=TorsiondriveWorkflow, attributes=attributes,
                         extras={"dihedrals": (9, 3, 2, 1)})
    # load up the ethane result
    result = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
    td_result = result.collection["[h:1][c:2]([h])([h])[c:3]([h:4])([h])[h]"]

    # now supply the correct data but wrong molecule
    with pytest.raises(MoleculeMissMatchError):
        entry.update_with_results(results=td_result)


def test_update_molecule_wrong_dihedral():
    """
    Make sure the when the same molecule but a different torsion is supplied we raise an error.
    """
    # make a new molecule entry
    occo = Molecule.from_file(file_path=get_data("OCCO.sdf"), file_format="sdf")
    attributes = get_molecule_cmiles(occo)
    entry = FittingEntry(name="occo", collection_workflow=TorsiondriveWorkflow, attributes=attributes,
                         extras={"dihedrals": (9, 3, 2, 1)})
    # now supply data for the correct molecule but wrong dihedral
    result = TorsionDriveCollectionResult.parse_file(get_data("occo.json"))
    with pytest.raises(DihedralSelectionError):
        entry.update_with_results(results=result.collection["[h][c:2]([h])([c:3]([h])([h])[o:4][h])[o:1][h]"])


def test_update_molecule_remapping():
    """
    Make sure that results are remapped when needed.
    """
    # make a new molecule entry
    occo = Molecule.from_file(file_path=get_data("OCCO.sdf"), file_format="sdf")
    attributes = get_molecule_cmiles(occo)
    entry = FittingEntry(name="occo", collection_workflow=TorsiondriveWorkflow, attributes=attributes,
                         extras={"dihedrals": (9, 3, 2, 1)})
    # now change to the correct dihedral
    entry.extras = {"dihedrals": (0, 1, 2, 3)}
    result = TorsionDriveCollectionResult.parse_file(get_data("occo.json"))
    # update the result wih no remapping
    entry.update_with_results(results=result.collection["[h][c:2]([h])([c:3]([h])([h])[o:4][h])[o:1][h]"])

    # no remapping is done here
    # make sure the gradients are correctly applied back
    normal_gradients = entry.collection_workflow[0].result[0].gradient

    # now get the molecule again in the wrong order
    can_occo = Molecule.from_file(file_path=get_data("can_occo.sdf"), file_format="sdf")
    can_attributes = get_molecule_cmiles(molecule=can_occo)
    can_entry = FittingEntry(name="can_occo", collection_workflow=TorsiondriveWorkflow, attributes=can_attributes, extras={"dihedrals": (2, 0, 1, 3)})
    # update with results that need to be remapped
    can_entry.update_with_results(results=result.collection["[h][c:2]([h])([c:3]([h])([h])[o:4][h])[o:1][h]"])

    mapped_gradients = can_entry.collection_workflow[0].result[0].gradient

    # now make sure they match
    _, atom_map = Molecule.are_isomorphic(can_occo, occo, return_atom_map=True)
    for i in range(len(normal_gradients)):
        assert normal_gradients[i].tolist() == mapped_gradients[atom_map[i]].tolist()


def test_fitting_add_optimizer():
    """
    Test adding optimizers to the fitting schema
    """

    fitting = FittingSchema(client="snowflake")
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


def test_get_optimizers():
    """
    Make sure that the optimizers in the workflow can be remade with the correct settings.
    """

    fitting = FittingSchema(client="snowflake")
    assert [] == fitting.get_optimizers
    # now add the optimizers
    fb = ForceBalanceOptimizer(penalty_type="L1")
    fitting.add_optimizer(optimizer=fb)
    assert [fb, ] == fitting.get_optimizers


def test_get_optimizer():
    """
    Make sure that the fitting schema can correctly remake a specific optimizer.
    """
    fitting = FittingSchema(client="snowflake")
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
    # occo has two torsions the same and ethane has 1 so only 3 unique tasks should be made
    assert schema.n_tasks == 3


def test_update_results_multiple():
    """
    Make sure the fitting schema can correctly apply any results to the correct tasks.
    """
    occo = Molecule.from_file(file_path=get_data("OCCO.sdf"), file_format="sdf")
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    schema = get_fitting_schema(molecules=[occo, ethane])
    assert schema.n_tasks == 3
    results = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
    schema.update_with_results(results=[results, ])
    results = TorsionDriveCollectionResult.parse_file(get_data("occo.json"))
    schema.update_with_results(results=[results, ])
    # now make sure there is only one task left
    tasks = set()
    for molecule in schema.tasks:
        for target in molecule.workflow.targets:
            for entry in target.entries:
                for task in entry.current_tasks():
                    tasks.add(task.job_id)

    assert len(tasks) == 1


def test_schema_to_qcsubmit_torsiondrives():
    """
    Make a qcsubmit dataset from the fitting schema.
    """
    occo = Molecule.from_file(file_path=get_data("OCCO.sdf"), file_format="sdf")
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    schema = get_fitting_schema(molecules=[occo, ethane])
    # make a torsiondrive dataset
    datasets = schema.generate_qcsubmit_datasets()
    assert len(datasets) == 1
    tdrive = datasets[0]
    # we should have two molecule and 3 tdrives in total
    assert tdrive.n_molecules == 2
    assert tdrive.n_records == 3
    # now add a result and run again
    result = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
    schema.update_with_results(results=[result, ])
    datasets = schema.generate_qcsubmit_datasets()

    tdrive2 = datasets[0]
    assert tdrive2.n_molecules == 1
    assert tdrive2.n_records == 2


def test_schema_to_qcsubmit_mixed():
    """
    Test exporting to qcsubmit datasets with a mixture of collection tasks.
    """
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    schema = get_fitting_schema(molecules=[ethane, ])
    td_target = schema.tasks[0].workflow.targets[0].copy(deep=True)
    td_target.target_name = "tdoptimizer"
    # now edit it to use optimizations
    td_target.entries[0].collection_workflow = HessianWorkflow
    schema.tasks[0].workflow.targets.append(td_target)

    datasets = schema.generate_qcsubmit_datasets()
    assert len(datasets) == 2
    assert isinstance(datasets[0], OptimizationDataset) is True
    assert isinstance(datasets[1], TorsiondriveDataset) is True




