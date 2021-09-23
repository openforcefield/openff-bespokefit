import json

from openff.fragmenter.fragment import FragmentationResult, PfizerFragmenter
from openff.toolkit.topology import Molecule

from openff.bespokefit.executor.services.fragmenter import worker


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
