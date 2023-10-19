"""QC generation caching."""
import hashlib
from typing import TypeVar, Union

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
        Molecule.from_smiles(task.smiles, allow_undefined_stereo=True),
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
            isomeric=True,
            explicit_hydrogens=True,
            mapped=True,
        )

        task.central_bond = (1, 2)

    else:
        canonical_smiles = canonical_molecule.to_smiles(
            isomeric=True,
            explicit_hydrogens=True,
            mapped=False,
        )

    task.smiles = canonical_smiles

    return task


def cached_compute_task(
    task: Union[HessianTask, OptimizationTask, Torsion1DTask],
    redis_connection: redis.Redis,
) -> str:
    """Check to see if a QC task has already been executed and, if not, send it to a worker."""
    if isinstance(task, Torsion1DTask):
        compute = worker.compute_torsion_drive
    elif isinstance(task, OptimizationTask):
        compute = worker.compute_optimization
    elif isinstance(task, HessianTask):
        compute = worker.compute_hessian
    else:
        raise NotImplementedError()

    # Canonicalize the task to improve the cache hit rate.
    task = _canonicalize_task(task)

    task_hash = hashlib.sha512(task.json().encode()).hexdigest()
    task_id = redis_connection.hget("qcgenerator:task-ids", task_hash)

    if task_id is not None:
        return task_id.decode()

    task_id = compute.delay(task_json=task.json()).id

    redis_connection.hset("qcgenerator:types", task_id, task.type)
    # Make sure to only set the hash after the type is set in case the connection
    # goes down before this information is entered and subsequently discarded.
    redis_connection.hset("qcgenerator:task-ids", task_hash, task_id)
    return task_id
