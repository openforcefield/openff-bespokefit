from typing import List, Optional, Union

import redis
from openff.fragmenter.fragment import (
    Fragment,
    FragmentationResult,
    PfizerFragmenter,
    WBOFragmenter,
    get_atom_index,
)
from pydantic import parse_raw_as

import openff.bespokefit
from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.utilities.celery import configure_celery_app
from openff.bespokefit.utilities.molecule import get_atom_symmetries

__settings = current_settings()

redis_connection = redis.Redis(
    host=__settings.BEFLOW_REDIS_ADDRESS,
    port=__settings.BEFLOW_REDIS_PORT,
    db=__settings.BEFLOW_REDIS_DB,
)
celery_app = configure_celery_app("fragmenter", redis_connection)


@celery_app.task(acks_late=True)
def fragment(
    cmiles: str, fragmenter_json: str, target_bond_smarts: Optional[List[str]]
) -> str:

    from openff.toolkit.topology import Molecule

    molecule: Molecule = Molecule.from_mapped_smiles(cmiles)

    if fragmenter_json != "null":
        # normal pathway
        fragmenter = parse_raw_as(
            Union[PfizerFragmenter, WBOFragmenter], fragmenter_json
        )
        return _deduplicate_fragments(
            fragmenter.fragment(molecule, target_bond_smarts=target_bond_smarts)
        ).json()

    elif fragmenter_json == "null" and target_bond_smarts:
        # no fragmentation and mock fragments
        all_matches = set()
        for target_smarts in target_bond_smarts:
            matches = molecule.chemical_environment_matches(query=target_smarts)
            for match in matches:
                all_matches.add(tuple(sorted(match)))

        fragments = []
        # mock one fragment per match
        for bond in all_matches:
            fragments.append(
                Fragment(
                    smiles=molecule.to_smiles(mapped=True),
                    # map indices are index + 1
                    bond_indices=(bond[0] + 1, bond[1] + 1),
                )
            )
        result = FragmentationResult(
            parent_smiles=molecule.to_smiles(mapped=True),
            fragments=fragments,
            provenance={
                "creator": openff.bespokefit.__package__,
                "version": openff.bespokefit.__version__,
            },
        )
        return _deduplicate_fragments(result).json()

    else:
        # no fragmentation and no mock fragments
        return "null"


def _deduplicate_fragments(
    fragmentation_result: FragmentationResult,
) -> FragmentationResult:
    """Remove symmetry equivalent fragments from the results."""
    from collections import defaultdict

    # group fragments which are the same
    fragments_by_smiles = defaultdict(list)
    for fragment_result in fragmentation_result.fragments:
        fragments_by_smiles[
            fragment_result.molecule.to_smiles(explicit_hydrogens=False)
        ].append(fragment_result)

    unique_fragments = []
    # remove duplicated symmetry equivalent fragments
    for fragments in fragments_by_smiles.values():
        if len(fragments) == 1:
            unique_fragments.extend(fragments)

        else:
            symmetry_groups = set()
            for fragment in fragments:
                bond_map = fragment.bond_indices
                fragment_mol = fragment.molecule
                # get the index of the atoms in the fragment
                atom1, atom2 = get_atom_index(
                    fragment_mol, bond_map[0]
                ), get_atom_index(fragment_mol, bond_map[1])
                symmetry_classes = get_atom_symmetries(fragment_mol)
                symmetry_group = tuple(
                    sorted([symmetry_classes[atom1], symmetry_classes[atom2]])
                )
                if symmetry_group not in symmetry_groups:
                    symmetry_groups.add(symmetry_group)
                    unique_fragments.append(fragment)

    fragmentation_result.fragments = unique_fragments

    return fragmentation_result
