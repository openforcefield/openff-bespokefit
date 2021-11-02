import hashlib

import redis
from openff.toolkit.topology import Molecule

from openff.bespokefit.executor.services.fragmenter import worker
from openff.bespokefit.executor.services.fragmenter.models import FragmenterPOSTBody


def cached_fragmentation_task(
    task: FragmenterPOSTBody, redis_connection: redis.Redis
) -> str:
    """
    Check if the fragmentation has been done before if not send it to a worker.
    """
    molecule: Molecule = Molecule.from_mapped_smiles(task.cmiles)
    task_string = (
        molecule.to_inchikey(fixed_hydrogens=True)
        + task.fragmenter.json()
        + str(task.target_bond_smarts)
    )
    task_hash = hashlib.sha512(task_string.encode()).hexdigest()
    task_id = redis_connection.hget("fragmenter:task-ids", task_hash)

    if task_id is not None:
        return task_id.decode()

    task_id = worker.fragment.delay(
        cmiles=task.cmiles,
        fragmenter_json=task.fragmenter.json(),
        target_bond_smarts=task.target_bond_smarts,
    ).id

    # store the result
    redis_connection.hset("fragmenter:task-ids", task_hash, task_id)
    return task_id
