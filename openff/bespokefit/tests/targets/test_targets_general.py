"""
Test all general target methods.
"""

import pytest
from openforcefield.topology import Molecule

from ...targets import Target, TorsionDrive1D
from ...targets.atom_selection import TorsionSelection
from ...utils import get_data


def test_provenance_extras():
    """
    Test that adding extra dependencies changes the provenance.
    """
    target = TorsionDrive1D()
    provenance = target.provenance()
    assert "qcsubmit" not in provenance
    assert "openforcefield" in provenance
    assert "chemper" in provenance
    assert "fragmenter" in provenance

    # now add qcsubmit and call again
    target._extra_dependencies.append("qcsubmit")
    provenance = target.provenance()
    assert "qcsubmit" in provenance


def test_enum_dict():
    """
    Make sure any declared enum fields are correctly serialized.
    """
    target = TorsionDrive1D()
    data = target.dict()
    assert data["torsion_selection"] == TorsionSelection.All.value
    # now remove the field
    target._enum_fields.remove("torsion_selection")
    data = target.dict()
    assert data["torsion_selection"] == TorsionSelection.All


@pytest.mark.parametrize("atoms", [
    pytest.param((0,), id="Single atom"),
    pytest.param((0, 1), id="Bond"),
    pytest.param((2, 0, 1), id="Angle"),
    pytest.param((2, 0, 1, 5), id="Torsion")
])
def test_new_single_smirks(atoms):
    """
    Test making a new smirks pattern and check it hits the correct atoms.
    """
    ethane = Molecule.from_file(get_data("ethane.sdf"))
    new_smirks = Target._get_new_single_graph_smirks(atoms=atoms, molecule=ethane)
    # now we need to make sure the new smirks hits the molecule
    matches = set(ethane.chemical_environment_matches(query=new_smirks))
    assert atoms in matches


@pytest.mark.parametrize("fragment_data", [
    pytest.param(("bace.sdf", "bace_frag1.sdf", (18, 10, 11, 17),  (6, 10, 11, 9)), id="BACE Fragment 1"),
    pytest.param(("bace.sdf", "bace_frag2.sdf", (19, 5, 6, 7), (12, 13, 5, 3)), id="BACE Fragment 2 torsion 1"),
    pytest.param(("bace.sdf", "bace_frag2.sdf", (23, 19, 5, 6), (10, 12, 13, 5)), id="BACE Fragment 2 torsion 2"),

])
def test_new_cluster_smirks(fragment_data):
    """
    Test making a new cluster graph smirks pattern based on a fragment and parent hits the correct atoms in both.
    """
    parent_file, fragment_file, parent_torsion, fragment_torsion = fragment_data
    parent = Molecule.from_file(get_data(parent_file), "sdf")
    fragment = Molecule.from_file(get_data(fragment_file), "sdf")
    new_smirks = Target._get_new_cluster_graph_smirks(atoms=[[parent_torsion, ], [fragment_torsion, ]], molecules=[parent, fragment])
    # now make sure the smirks hit the correct atoms
    assert parent_torsion in set(parent.chemical_environment_matches(query=new_smirks))
    assert fragment_torsion in set(fragment.chemical_environment_matches(query=new_smirks))


@pytest.mark.parametrize("molecules", [
    pytest.param(("bace.sdf", "bace.sdf", {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9, 10: 10, 11: 11, 12: 12, 13: 13, 14: 14, 15: 15, 16: 16, 17: 17, 18: 18, 19: 19, 20: 20, 21: 21, 22: 22, 23: 23, 24: 24, 25: 25, 26: 26, 27: 27, 28: 28, 29: 48, 30: 30, 31: 31, 32: 32, 33: 33, 34: 34, 35: 35, 36: 36, 37: 37, 38: 38, 39: 39, 40: 40, 41: 41, 42: 42, 43: 43, 44: 44, 45: 45, 46: 46, 47: 47, 48: 29}), id="Same molecule"),
    pytest.param(("bace.sdf", "bace_frag1.sdf", {0: 7, 2: 8, 6: 9, 10: 10, 7: 18, 3: 6, 19: 38, 11: 11, 8: 17, 4: 15, 1: 14, 5: 13, 9: 12, 21: 34, 17: 35, 13: 36, 20: 37, 18: 33, 14: 32, 12: 31}), id="BACE parent fragment1 mapping"),
    pytest.param(("bace.sdf", "bace_frag2.sdf", {0: 9, 1: 8, 3: 7, 5: 6, 4: 18, 2: 10, 22: 38, 13: 5, 7: 24, 15: 1, 6: 2, 16: 4, 36: 30, 14: 0, 33: 26, 34: 27, 35: 28, 17: 25, 12: 19, 10: 20, 8: 21, 9: 22, 11: 23, 30: 46, 31: 47, 26: 44, 27: 45, 24: 42, 25: 43, 28: 40, 29: 41, 32: 39, 21: 31, 19: 32, 18: 33}), id="BACE parent fragment2 mapping")
])
def test_parent_fragment_mapping(molecules):
    """
    Test generating a parent fragment mapping.
    """
    molecule1, molecule2, atom_map = molecules
    mol1 = Molecule.from_file(get_data(molecule1), "sdf")
    mol2 = Molecule.from_file(get_data(molecule2), "sdf")
    mapping = Target._get_fragment_parent_mapping(fragment=mol2, parent=mol1)
    assert mapping == atom_map
