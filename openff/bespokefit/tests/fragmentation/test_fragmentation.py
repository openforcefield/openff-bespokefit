"""
Test specific fragmentation engines.
"""

from openff.toolkit.topology import Molecule

from openff.bespokefit.fragmentation import PfizerFragmenter, WBOFragmenter


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
    provenance = WBOFragmenter.provenance()
    assert "openff-fragmenter" in provenance
    assert "openff-toolkit" in provenance
    assert "openeye" in provenance


def test_wbo_fragmentation():
    """
    Test that a molecule can be fragmented successfully and produce the expected results.
    """
    # bace can be fragmented into 3 parts 2 of which are the same
    engine = WBOFragmenter()
    engine.keep_non_rotor_ring_substituents = True
    bace = Molecule.from_mapped_smiles(
        "[H:30][c:6]1[c:7]([c:8]([c:16]([c:4]([c:5]1[H:29])[C@@:3]2([C:22](=[O:23])[N:20]([C:18](=[N+:17]2[H:37])[N:19]([H:38])[H:42])[C:21]([H:39])([H:40])[H:41])[C:2]([H:27])([H:28])[C:1]([H:24])([H:25])[H:26])[H:36])[c:9]3[c:10]([c:11]([c:12]([c:13]([c:15]3[H:35])[Cl:14])[H:34])[H:33])[H:32])[H:31]"
    )
    fragment_data = engine.fragment(molecule=bace)
    assert len(fragment_data) == 3
    fragments = [fragment.fragment_molecule for fragment in fragment_data]
    # make sure the fragments are correct
    fragments_smiles = [
        "[H:14][c:1]1[c:2]([c:5]([c:10]([c:6]([c:3]1[H:16])[H:19])[c:11]2[c:7]([c:4]([c:8]([c:12]([c:9]2[H:22])[Cl:13])[H:21])[H:17])[H:20])[H:18])[H:15]",
        "[H:17][c:1]1[c:2]([c:4]([c:6]([c:5]([c:3]1[H:19])[H:21])[C@@:9]2([C:7](=[O:16])[N:13]([C:8](=[N+:14]2[H:30])[N:15]([H:31])[H:32])[C:11]([H:25])([H:26])[H:27])[C:12]([H:28])([H:29])[C:10]([H:22])([H:23])[H:24])[H:20])[H:18]",
    ]
    for smiles in fragments_smiles:
        frag_mol = Molecule.from_mapped_smiles(smiles)
        assert frag_mol in fragments

    # check the mapping
    assert fragment_data[0].fragment_parent_mapping == {
        0: 7,
        1: 6,
        2: 1,
        3: 2,
        4: 3,
        5: 4,
        6: 5,
        8: 29,
        9: 30,
        10: 31,
        11: 32,
        12: 33,
        13: 34,
        14: 35,
        15: 36,
        16: 37,
        17: 38,
        18: 39,
        19: 40,
        20: 41,
        21: 0,
    }
    assert fragment_data[1].fragment_parent_mapping == {
        0: 41,
        1: 2,
        2: 1,
        3: 6,
        4: 5,
        5: 4,
        6: 3,
        8: 29,
        9: 8,
        10: 9,
        11: 10,
        12: 11,
        13: 12,
        14: 13,
        15: 14,
        16: 15,
        17: 16,
        18: 17,
        19: 18,
        20: 19,
        21: 20,
        22: 21,
        23: 22,
        24: 23,
        25: 24,
        26: 25,
        27: 26,
        28: 27,
        29: 28,
        30: 7,
        31: 0,
    }
    assert (
        fragment_data[1].fragment_parent_mapping
        == fragment_data[2].fragment_parent_mapping
    )

    # make sure all of the central bonds are different
    torsions = set([fragment.parent_torsion for fragment in fragment_data])
    assert len(torsions) == 3
    # make sure that each torsion id is a correct torsion in the parent molecule
    for torsion in torsions:
        fragment_data[0].parent_molecule.get_bond_between(*torsion)


def test_pfizer_fragmentation():
    """Make sure the Pfizer fragmenation method produces the expected results and parent mapping.
    Produces slightly different fragments to the WBO method hence the test is split.
    """
    # bace can be fragmented into 3 parts 2 of which are the same
    engine = PfizerFragmenter()
    bace = Molecule.from_mapped_smiles(
        "[H:30][c:6]1[c:7]([c:8]([c:16]([c:4]([c:5]1[H:29])[C@@:3]2([C:22](=[O:23])[N:20]([C:18](=[N+:17]2[H:37])[N:19]([H:38])[H:42])[C:21]([H:39])([H:40])[H:41])[C:2]([H:27])([H:28])[C:1]([H:24])([H:25])[H:26])[H:36])[c:9]3[c:10]([c:11]([c:12]([c:13]([c:15]3[H:35])[Cl:14])[H:34])[H:33])[H:32])[H:31]"
    )
    fragment_data = engine.fragment(molecule=bace)
    assert len(fragment_data) == 3
    fragments = [fragment.fragment_molecule for fragment in fragment_data]

    fragments_smiles = [
        "[H:1][c:2]1[c:7]([c:6]([c:5]([c:4]([c:3]1[H:22])[H:21])[c:10]2[c:15]([c:14]([c:13]([c:12]([c:11]2[H:20])[H:19])[H:18])[H:17])[H:16])[H:9])[H:8]",
        "[H:1][c:2]1[c:7]([c:6]([c:5]([c:4]([c:3]1[H:30])[H:29])[C@@:10]2([C:11](=[O:12])[N:13]([C:14](=[N+:15]2[H:16])[H:17])[C:18]([H:19])([H:20])[H:21])[C:22]([H:23])([H:24])[C:25]([H:26])([H:27])[H:28])[H:9])[H:8]",
    ]
    for smiles in fragments_smiles:
        frag_mol = Molecule.from_mapped_smiles(smiles)
        assert frag_mol in fragments

    # check the mapping
    assert fragment_data[0].fragment_parent_mapping == {
        0: 7,
        1: 6,
        2: 1,
        3: 2,
        4: 3,
        5: 4,
        6: 5,
        8: 29,
        9: 30,
        10: 31,
        11: 32,
        12: 33,
        13: 34,
        14: 35,
        15: 36,
        17: 38,
        18: 39,
        19: 40,
        20: 41,
        21: 0,
    }
    assert fragment_data[1].fragment_parent_mapping == {
        0: 41,
        1: 2,
        2: 1,
        3: 6,
        4: 5,
        5: 4,
        6: 3,
        8: 29,
        9: 8,
        10: 9,
        11: 10,
        12: 11,
        13: 12,
        14: 13,
        15: 14,
        17: 18,
        18: 19,
        19: 20,
        20: 21,
        21: 22,
        22: 23,
        23: 24,
        24: 25,
        25: 26,
        26: 27,
        27: 28,
        28: 7,
        29: 0,
    }
    assert (
        fragment_data[1].fragment_parent_mapping
        == fragment_data[2].fragment_parent_mapping
    )

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
