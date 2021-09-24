import hashlib
from typing import Union

import redis

from openff.bespokefit.executor.services.qcgenerator import worker
from openff.bespokefit.schema.tasks import HessianTask, OptimizationTask, Torsion1DTask


def cached_compute_task(
    task: Union[HessianTask, OptimizationTask, Torsion1DTask],
    redis_connection: redis.Redis,
) -> str:
    """Checks to see if a QC task has already been executed and if not send it to a
    worker.
    """

    if isinstance(task, Torsion1DTask):
        compute = worker.compute_torsion_drive
    elif isinstance(task, OptimizationTask):
        compute = worker.compute_optimization
    elif isinstance(task, HessianTask):
        compute = worker.compute_hessian
    else:
        raise NotImplementedError()

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
