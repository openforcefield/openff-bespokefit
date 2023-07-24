import json
import os

from openff.fragmenter.fragment import (
    FragmentationResult,
    PfizerFragmenter,
    WBOFragmenter,
)
from openff.toolkit.topology import Molecule
from openff.utilities import get_data_file_path

from openff.bespokefit.executor.services.fragmenter import worker
from openff.bespokefit.workflows.bespoke import _DEFAULT_ROTATABLE_SMIRKS


def test_fragment():
    molecule = Molecule.from_smiles("CCCCCC")

    result_json = worker.fragment(
        cmiles=molecule.to_smiles(mapped=True),
        fragmenter_json=PfizerFragmenter().json(),
        target_bond_smarts=["[#6]-[#6]-[#6:1]-[#6:2]-[#6]-[#6]"],
    )
    assert isinstance(result_json, str)

    result_dict = json.loads(result_json)
    assert isinstance(result_dict, dict)

    result = FragmentationResult.parse_obj(result_dict)

    are_isomorphic, _ = Molecule.are_isomorphic(
        molecule, result.parent_molecule, return_atom_map=True
    )

    assert are_isomorphic
    assert len(result.fragments) == 1

    assert result.provenance["options"]["scheme"] == "Pfizer"


def test_fragment_mock(bace):
    """
    Test mocking a fragmentation result, when we want to scan a torsion but not fragment the molecule.
    """

    result_json = worker.fragment(
        cmiles=bace.to_smiles(mapped=True),
        fragmenter_json="null",
        target_bond_smarts=[_DEFAULT_ROTATABLE_SMIRKS],
    )

    result = FragmentationResult.parse_raw(result_json)
    assert len(result.fragments) == 3
    bonds_and_fragments = result.fragments_by_bond
    assert (11, 12) in bonds_and_fragments
    assert (6, 7) in bonds_and_fragments
    assert (6, 20) in bonds_and_fragments
    assert result.provenance["creator"] == "openff.bespokefit"


def test_fragmentation_skip(bace):
    """
    Make sure we got back None when we want to skip fragmentation and not scan a torsion.
    """

    result_json = worker.fragment(
        cmiles=bace.to_smiles(mapped=True),
        fragmenter_json="null",
        target_bond_smarts=None,
    )

    assert result_json == "null"


def test_fragmentation_symmetry_fragments():
    """Make sure symmetry equivalent fragments are filtered"""

    # molecule has symmetry equivalent torsions
    molecule = Molecule.from_smiles("COP(=O)(O)OC")

    result_json = worker.fragment(
        cmiles=molecule.to_smiles(mapped=True),
        fragmenter_json=PfizerFragmenter().json(),
        target_bond_smarts=[_DEFAULT_ROTATABLE_SMIRKS],
    )
    result = FragmentationResult.parse_raw(result_json)

    assert len(result.fragments) == 1
    assert len(result.fragment_molecules) == 1


def test_fragmentation_equivalent_no_symmetry():
    """Make sure duplicated fragments which are not symmetry equivalent are not filtered."""

    bace_folder = os.path.dirname(
        get_data_file_path(
            os.path.join("test", "molecules", "bace", "bace_parent.sdf"),
            "openff.bespokefit",
        )
    )

    molecule = Molecule.from_file(
        file_path=os.path.join(bace_folder, "bace_parent.sdf"),
        file_format="sdf",
    )

    result_json = worker.fragment(
        cmiles=molecule.to_smiles(mapped=True),
        fragmenter_json=WBOFragmenter().json(),
        target_bond_smarts=[_DEFAULT_ROTATABLE_SMIRKS],
    )

    result = FragmentationResult.parse_raw(result_json)
    assert len(result.fragments) == 3
    unique_fragments = set([fragment.molecule for fragment in result.fragments])
    assert len(unique_fragments) == 2
    reference_fragments = [
        Molecule.from_file(
            file_path=os.path.join(bace_folder, f"bace_frag{i + 1}.sdf"),
            file_format="sdf",
        )
        for i in range(2)
    ]
    for fragment in reference_fragments:
        assert fragment in unique_fragments
