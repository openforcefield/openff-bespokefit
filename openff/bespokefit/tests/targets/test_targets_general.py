"""
Test all general target methods.
"""

import pytest
from openff.qcsubmit.common_structures import QCSpec
from openforcefield.topology import Molecule
from typing_extensions import Literal

from openff.bespokefit.schema import TargetSchema
from openff.bespokefit.targets import Target
from openff.bespokefit.utils import get_data, get_molecule_cmiles


class DummyTarget(Target):
    collection_workflow: Literal["torsion1d", "optimization", "hessian", "test"] = "torsion1d"
    description = "A dummy class for testing general methods of the base class."

    def prep_for_fitting(self, fitting_target: TargetSchema) -> None:
        pass

    def local_reference_collection(self, fitting_target: TargetSchema) -> TargetSchema:
        pass


def test_provenance_extras():
    """
    Test that adding extra dependencies changes the provenance.
    """
    target = DummyTarget()
    provenance = target.provenance()
    assert "qcsubmit" in provenance
    assert "openforcefield" in provenance
    assert "bespokefit" in provenance
    assert "openforcefield" in provenance
    assert "openforcefields" in provenance
    assert provenance["target"] == target.name

    # now add qcsubmit and call again
    target._extra_dependencies.append("openeye")
    provenance = target.provenance()
    assert "openeye" in provenance


def test_generate_target_schema():
    """
    Generate a target schema for this target.
    """
    target = DummyTarget()
    # change the spec
    spec = QCSpec(method="ani2x", basis=None, program="torchani")
    target.qc_spec = spec
    schema = target.generate_target_schema()
    assert schema.target_name == target.name
    assert schema.qc_spec == target.qc_spec
    assert schema.collection_workflow == target.collection_workflow
    assert schema.settings == target.dict()


@pytest.mark.parametrize("collection_workflow", [
    pytest.param("torsion1d", id="torsion1d"),
    pytest.param("optimization", id="optimizations"),
    pytest.param("hessian", id="hessian")
])
def test_generate_fitting_task(collection_workflow):
    """
    Make sure the correct fitting task is made based on the collection workflow.
    """
    target = DummyTarget()
    target.collection_workflow = collection_workflow
    molecule = Molecule.from_file(get_data("ethanol.sdf"))
    task_schema = target.generate_fitting_task(molecule=molecule, fragment=False, attributes=get_molecule_cmiles(molecule), dihedrals=[(8, 2, 1, 0)])
    assert task_schema.task_type == collection_workflow


def test_missing_task_type():
    """
    Make sure an error is raised if we do not know how to generate the task.
    """
    target = DummyTarget()
    target.collection_workflow = "test"
    molecule = Molecule.from_file(get_data("ethanol.sdf"))
    with pytest.raises(NotImplementedError):
        _ = target.generate_fitting_task(molecule=molecule, fragment=False,
                                                   attributes=get_molecule_cmiles(molecule), dihedrals=[(8, 2, 1, 0)])