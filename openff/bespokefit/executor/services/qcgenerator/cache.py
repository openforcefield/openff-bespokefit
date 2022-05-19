import hashlib
from typing import Optional, TypeVar, Union

import redis
from openff.toolkit.topology import Molecule

from openff.bespokefit.executor.services.qcgenerator import worker
from openff.bespokefit.schema.tasks import HessianTask, OptimizationTask, Torsion1DTask
from openff.bespokefit.utilities.molecule import canonical_order_atoms

_T = TypeVar("_T", HessianTask, OptimizationTask, Torsion1DTask)


def _canonicalize_task(task: _T) -> _T:

    task = task.copy(deep=True)

    # Ensure the SMILES has a canonical ordering to help ensure cache hits.
    canonical_molecule = canonical_order_atoms(
        Molecule.from_smiles(task.smiles, allow_undefined_stereo=True)
    )

    if isinstance(task, Torsion1DTask):

        map_to_atom_index = {
            j: i for i, j in canonical_molecule.properties["atom_map"].items()
        }

        central_atom_indices = sorted(
            map_to_atom_index[task.central_bond[i]] for i in (0, 1)
        )
        canonical_molecule.properties["atom_map"] = {
            atom_index: (i + 1) for i, atom_index in enumerate(central_atom_indices)
        }

        canonical_smiles = canonical_molecule.to_smiles(
            isomeric=True, explicit_hydrogens=True, mapped=True
        )

        task.central_bond = (1, 2)

    else:

        canonical_smiles = canonical_molecule.to_smiles(
            isomeric=True, explicit_hydrogens=True, mapped=False
        )

    task.smiles = canonical_smiles

    return task


def _sha256_hash(contents: str) -> str:
    return hashlib.sha512(contents.encode()).hexdigest()


def _retrieve_cached_task_id(
    task_hash: str, redis_connection: redis.Redis
) -> Optional[str]:
    """Retrieve the task ID of a cached QC task if present in the redis cache"""

    task_id = redis_connection.hget("qcgenerator:task-ids", task_hash)

    return None if task_id is None else task_id.decode()


def _cache_task_id(
    task_id: str, task_type: str, task_hash: str, redis_connection: redis.Redis
):

    redis_connection.hset("qcgenerator:types", task_id, task_type)
    # Make sure to only set the hash after the type is set in case the connection
    # goes down before this information is entered and subsequently discarded.
    redis_connection.hset("qcgenerator:task-ids", task_hash, task_id)


def _compute_torsion_drive_task(
    task: Torsion1DTask, redis_connection: redis.Redis
) -> str:

    task_hash = _sha256_hash(task.json())
    task_id = _retrieve_cached_task_id(task_hash, redis_connection)

    if task_id is not None:
        return task_id

    torsion_drive_task = task.copy(deep=True)
    torsion_drive_task.sp_specification = None

    torsion_drive_hash = _sha256_hash(torsion_drive_task.json())
    torsion_drive_id = _retrieve_cached_task_id(torsion_drive_hash, redis_connection)

    if torsion_drive_id is None:

        torsion_drive_id = worker.compute_torsion_drive.delay(task_json=task.json()).id

        _cache_task_id(
            torsion_drive_id, task.type, torsion_drive_hash, redis_connection
        )

    if task.sp_specification is None:
        return torsion_drive_id

    single_point_id = (
        (
            worker.wait_for_task.s(torsion_drive_id)
            | worker.evaluate_torsion_drive.s(
                model_json=task.sp_specification.model.json(),
                program=task.sp_specification.program,
            )
        )
        .delay()
        .id
    )

    _cache_task_id(single_point_id, task.type, task_hash, redis_connection)
    return single_point_id


def cached_compute_task(
    task: Union[HessianTask, OptimizationTask, Torsion1DTask],
    redis_connection: redis.Redis,
) -> str:
    """Checks to see if a QC task has already been executed and if not send it to a
    worker.
    """

    if isinstance(task, Torsion1DTask):
        return _compute_torsion_drive_task(task, redis_connection)
    elif isinstance(task, OptimizationTask):
        compute = worker.compute_optimization
    elif isinstance(task, HessianTask):
        compute = worker.compute_hessian
    else:
        raise NotImplementedError()

    # Canonicalize the task to improve the cache hit rate.
    task = _canonicalize_task(task)

    task_hash = _sha256_hash(task.json())
    task_id = _retrieve_cached_task_id(task_hash, redis_connection)

    if task_id is not None:
        return task_id

    task_id = compute.delay(task_json=task.json()).id
    _cache_task_id(task_id, task.type, task_hash, redis_connection)

    return task_id
