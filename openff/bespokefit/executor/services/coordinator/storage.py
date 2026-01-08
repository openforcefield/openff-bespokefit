import pickle
from enum import Enum
from typing import List, Optional, Set, Union

from openff.bespokefit.executor.services.coordinator.models import CoordinatorTask
from openff.bespokefit.executor.services.coordinator.stages import (
    FragmentationStage,
    OptimizationStage,
    QCGenerationStage,
)
from openff.bespokefit.executor.utilities.redis import connect_to_default_redis
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema


class TaskStatus(str, Enum):
    waiting = "waiting"
    running = "running"
    complete = "complete"


_QUEUE_NAMES = {
    TaskStatus.waiting: "coordinator:tasks:waiting",
    TaskStatus.running: "coordinator:tasks:running",
    TaskStatus.complete: "coordinator:tasks:complete",
}


def _task_id_to_key(task_id: Union[str, int]) -> str:
    return f"coordinator:task:{task_id}"


def get_task(task_id: Union[str, int]) -> CoordinatorTask:
    connection = connect_to_default_redis()

    task_pickle = connection.get(_task_id_to_key(task_id))

    if task_pickle is None:
        raise IndexError(f"{task_id} was not found")

    return CoordinatorTask.parse_obj(pickle.loads(task_pickle))


def get_task_ids(
    skip: int = 0,
    limit: Optional[int] = None,
    status: Optional[Union[TaskStatus, Set[TaskStatus]]] = None,
) -> List[int]:
    connection = connect_to_default_redis()

    possible_status = [TaskStatus.waiting, TaskStatus.running, TaskStatus.complete]

    if status is not None and isinstance(status, TaskStatus):
        status = {status}
    elif status is None:
        status = {TaskStatus.waiting, TaskStatus.running, TaskStatus.complete}

    ordered_status = [value for value in possible_status if value in status]

    task_ids = [
        int(task_id)
        for task_status in ordered_status
        for task_id in connection.lrange(_QUEUE_NAMES[task_status], 0, -1)
    ][skip : (skip + limit if limit is not None else None)]

    return task_ids


def create_task(
    input_schema: BespokeOptimizationSchema,
    stages: Optional[
        List[Union[FragmentationStage, QCGenerationStage, OptimizationStage]]
    ] = None,
) -> int:
    connection = connect_to_default_redis()

    task_id = connection.incr("coordinator:id-counter")

    stages = (
        stages
        if stages is not None
        else [FragmentationStage(), QCGenerationStage(), OptimizationStage()]
    )

    task = CoordinatorTask(
        id=str(task_id),
        input_schema=input_schema,
        pending_stages=stages,
    )
    task.input_schema.id = task_id

    task_key = _task_id_to_key(task_id)

    connection.set(task_key, pickle.dumps(task.dict()))
    connection.rpush(_QUEUE_NAMES[TaskStatus.waiting], task_id)

    return task_id


def get_n_tasks(status: Optional[TaskStatus] = None) -> int:
    connection = connect_to_default_redis()

    return sum(
        connection.llen(queue)
        for queue_name, queue in _QUEUE_NAMES.items()
        if status is None or queue_name == status
    )


def peek_task_status(status: TaskStatus) -> Optional[int]:
    connection = connect_to_default_redis()

    task_id = connection.lindex(_QUEUE_NAMES[status], 0)
    return None if task_id is None else int(task_id)


def pop_task_status(status: TaskStatus) -> Optional[int]:
    assert status != TaskStatus.complete, "complete tasks cannot be modified"

    connection = connect_to_default_redis()

    task_id = connection.lpop(_QUEUE_NAMES[status])
    return None if task_id is None else int(task_id)


def push_task_status(task_id: int, status: TaskStatus):
    connection = connect_to_default_redis()
    return connection.rpush(_QUEUE_NAMES[status], task_id)


def save_task(task: CoordinatorTask):
    connection = connect_to_default_redis()
    connection.set(_task_id_to_key(int(task.id)), pickle.dumps(task.dict()))


def snapshot_task_status(status: TaskStatus) -> List[int]:
    connection = connect_to_default_redis()
    task_ids = connection.lrange(_QUEUE_NAMES[status], 0, -1)
    return [int(task_id) for task_id in task_ids]


def remove_task_status(task_id: int, status: TaskStatus) -> int:
    connection = connect_to_default_redis()
    count = connection.lrem(_QUEUE_NAMES[status], 0, str(task_id))
    return count
