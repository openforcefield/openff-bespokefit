from typing import List, Union

import redis
from openff.fragmenter.fragment import PfizerFragmenter, WBOFragmenter
from pydantic import parse_raw_as

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.utilities.celery import configure_celery_app

redis_connection = redis.Redis(
    host=settings.BEFLOW_REDIS_ADDRESS,
    port=settings.BEFLOW_REDIS_PORT,
    db=settings.BEFLOW_REDIS_DB,
)
celery_app = configure_celery_app("fragmenter", redis_connection)


@celery_app.task(acks_late=True)
def fragment(cmiles: str, fragmenter_json: str, target_bond_smarts: List[str]) -> str:

    from openff.toolkit.topology import Molecule

    fragmenter = parse_raw_as(Union[PfizerFragmenter, WBOFragmenter], fragmenter_json)

    molecule = Molecule.from_mapped_smiles(cmiles)
    return fragmenter.fragment(molecule, target_bond_smarts=target_bond_smarts).json()
