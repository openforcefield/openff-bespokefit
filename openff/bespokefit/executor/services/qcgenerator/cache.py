import hashlib
from typing import TYPE_CHECKING, Optional, TypeVar, Union

import redis
from openff.toolkit.topology import Molecule

from openff.bespokefit.executor.services.qcgenerator import worker
from openff.bespokefit.schema.tasks import (
    BaseTaskSpec,
    HessianTask,
    OptimizationTask,
    Torsion1DTask,
)
from openff.bespokefit.utilities.molecule import canonical_order_atoms

if TYPE_CHECKING:
    # Only use as a type hint. Use `celery_app.AsyncResult` to initialize
    from celery.result import AsyncResult

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

    elif isinstance(task, (HessianTask, OptimizationTask)):

        canonical_smiles = canonical_molecule.to_smiles(
            isomeric=True, explicit_hydrogens=True, mapped=False
        )

    else:
        raise NotImplementedError()

    task.smiles = canonical_smiles

    return task


def _hash_task(task: BaseTaskSpec) -> str:
    """Returns a hashed representation of a QC task"""
    return hashlib.sha512(task.json().encode()).hexdigest()


def _retrieve_cached_task_id(
    task_hash: str, redis_connection: redis.Redis
) -> Optional[str]:
    """Retrieve the task ID of a cached QC task if present in the redis cache"""

    task_id = redis_connection.hget("qcgenerator:task-ids", task_hash)

    return None if task_id is None else task_id.decode()


def _cache_task_id(
    task_id: str, task_type: str, task_hash: str, redis_connection: redis.Redis
):
    """Store the ID of a running QC task in the QC task cache."""

    redis_connection.hset("qcgenerator:types", task_id, task_type)
    # Make sure to only set the hash after the type is set in case the connection
    # goes down before this information is entered and subsequently discarded.
    redis_connection.hset("qcgenerator:task-ids", task_hash, task_id)


def _compute_hessian_task() -> str:
    raise NotImplementedError()


def _compute_optimization_task(task: OptimizationTask):

    if task.pre_optimization_spec is not None or task.evaluation_spec is not None:
        raise NotImplementedError()

    task_id = worker.compute_optimization.delay(
        smiles=task.smiles,
        optimization_spec_json=task.optimization_spec.json(),
        n_conformers=task.n_conformers,
    ).id

    return task_id


def _compute_torsion_drive_task(
    task: Torsion1DTask, redis_connection: redis.Redis
) -> str:
    """Submit a torsion drive to celery, optionally chaining together a torsion
    drive followed by a single point energy re-evaluation."""

    task_id = None

    torsion_drive_task = task.copy(deep=True)
    torsion_drive_task.evaluation_spec = None

    torsion_drive_hash = _hash_task(torsion_drive_task)
    torsion_drive_id = _retrieve_cached_task_id(torsion_drive_hash, redis_connection)

    if torsion_drive_id is None:

        # There are no cached torsion drives at the 'pre-optimise' level of theory
        # we need to run a torsion drive and then optionally a single point
        if task.evaluation_spec is None:

            torsion_drive_id = worker.compute_torsion_drive.delay(
                smiles=task.smiles,
                central_bond=task.central_bond,
                grid_spacing=task.grid_spacing,
                scan_range=task.scan_range,
                optimization_spec_json=task.optimization_spec,
            ).id

        else:

            task_future: AsyncResult = (
                worker.compute_torsion_drive.s(task_json=task.json())
                | worker.re_evaluate_torsion_drive.s(
                    evaluation_spec_json=task.evaluation_spec.json(),
                )
            ).delay()

            torsion_drive_id = task_future.parent.id
            task_id = task_future.id

        _cache_task_id(
            torsion_drive_id, task.type, torsion_drive_hash, redis_connection
        )

    if task.evaluation_spec is None:
        return torsion_drive_id

    if task_id is None:

        # Handle the case where we have a running torsion drive that we need to
        # append a single point calculation to the end of.
        task_id = (
            (
                worker.wait_for_task.s(torsion_drive_id)
                | worker.re_evaluate_torsion_drive.s(
                    evaluation_spec_json=task.evaluation_spec.json(),
                )
            )
            .delay()
            .id
        )

    return task_id


def cached_compute_task(
    task: Union[HessianTask, OptimizationTask, Torsion1DTask],
    redis_connection: redis.Redis,
) -> str:
    """Checks to see if a QC task has already been executed and if not send it to a
    worker.
    """

    # Canonicalize the task to improve the cache hit rate.
    task = _canonicalize_task(task)

    task_hash = _hash_task(task)
    task_id = _retrieve_cached_task_id(task_hash, redis_connection)

    if task_id is not None:
        return task_id

    if isinstance(task, Torsion1DTask):
        task_id = _compute_torsion_drive_task(task, redis_connection)
    elif isinstance(task, OptimizationTask):
        task_id = _compute_optimization_task(task)
    elif isinstance(task, HessianTask):
        task_id = _compute_hessian_task()
    else:
        raise NotImplementedError()

    _cache_task_id(task_id, task.type, task_hash, redis_connection)
    return task_id
