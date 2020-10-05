"""
Test all parts of the fitting schema.
"""

from typing import Tuple

import pytest
from openforcefield.topology import Molecule

from qcsubmit.common_structures import QCSpec
from qcsubmit.results import TorsionDriveCollectionResult

from ...collection_workflows import (
    CollectionMethod,
    HessianWorkflow,
    Precedence,
    TorsiondriveWorkflow,
    WorkflowStage,
)
from ...common_structures import Status
from ...exceptions import (
    DihedralSelectionError,
    MissingReferenceError,
    MissingWorkflowError,
    MoleculeMissMatchError,
)
from ...schema.fitting import FittingEntry
from ...schema.smirks import AtomSmirks
from ...utils import get_data, get_molecule_cmiles, get_torsiondrive_index


def ethane_fitting_entry() -> Tuple[FittingEntry, Molecule]:
    """
    Return the ethane fitting entry.
    """
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    attributes = get_molecule_cmiles(molecule=ethane)
    entry = FittingEntry(name="ethane", attributes=attributes, extras={"dihedrals": (2, 0, 1, 5)})
    return entry, ethane


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
    tasks = entry.current_tasks()
    assert len(tasks) == 1
    # now add some tasks that can be done in parallel
    entry.collection_workflow = HessianWorkflow
    assert len(entry.current_tasks()) == 1
    # now allow both the opt and hessian to be done in parallel
    entry.collection_workflow[0].precedence = Precedence.Parallel
    entry.collection_workflow[1].precedence = Precedence.Parallel
    tasks = entry.current_tasks()
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
