"""
Test specific fragmentation engines.
"""
import pytest
from openforcefield.topology import Molecule

from openff.bespokefit.fragmentation import WBOFragmenter
from openff.bespokefit.utils import get_data


def test_is_available():
    """
    Make sure that the environment is checked for dependencies, as we install openeye and fragmenter in the test env this should
    be true.
    """
    assert WBOFragmenter.is_available() is True


def test_provenance():
    """
    Make sure the openeye and fragmenter versions are captured.
    """
    engine = WBOFragmenter()
    provenance = engine.provenance()
    assert "fragmenter" in provenance
    assert "openeye" in provenance


def test_normal_fragmentation():
    """
    Test that a molecule can be fragmented successfully and produce the expected results.
    """
    # bace can be fragmented into 3 parts 2 of which are the same
    engine = WBOFragmenter()
    engine.keep_non_rotor_ring_substituents = False
    bace = Molecule.from_file(file_path=get_data("bace_parent.sdf"), file_format="sdf")
    fragment_data = engine.fragment(molecule=bace)
    assert len(fragment_data) == 3

    fragments = [fragment.fragment_molecule for fragment in fragment_data]
    # make sure the fragments are correct
    for fragment in ["bace_frag1.sdf", "bace_frag2.sdf"]:
        frag_mol = Molecule.from_file(file_path=get_data(fragment), file_format="sdf")
        assert frag_mol in fragments

    # make sure all of the central bonds are different
    torsions = set([fragment.parent_torsion for fragment in fragment_data])
    assert len(torsions) == 3


def test_torsiondrive_fragmentation_fail():
    """
    Test torsiondrive fragmentation when fragmenter can not make a fragment due to no target bonds being found.
    """
    engine = WBOFragmenter()
    mol = Molecule.from_smiles(smiles="BrCO")
    fragment_data = engine.fragment(molecule=mol)
    assert len(fragment_data) == 0
