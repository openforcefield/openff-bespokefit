from typing import List, Optional, Union

import redis
from openff.fragmenter.fragment import (
    Fragment,
    FragmentationResult,
    PfizerFragmenter,
    WBOFragmenter,
)
from pydantic import parse_raw_as

import openff.bespokefit
from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.utilities.celery import configure_celery_app

redis_connection = redis.Redis(
    host=settings.BEFLOW_REDIS_ADDRESS,
    port=settings.BEFLOW_REDIS_PORT,
    db=settings.BEFLOW_REDIS_DB,
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
        return fragmenter.fragment(
            molecule, target_bond_smarts=target_bond_smarts
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
        return result.json()

    else:
        # no fragmentation and no mock fragments
        return "null"
