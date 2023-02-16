import pytest

from openff.bespokefit.executor.services.coordinator.models import CoordinatorTask
from openff.bespokefit.executor.services.coordinator.storage import (
    TaskStatus,
    _task_id_to_key,
    create_task,
    get_n_tasks,
    get_task,
    get_task_ids,
    peek_task_status,
    pop_task_status,
    push_task_status,
    save_task,
)


def test_task_id_to_key():
    assert _task_id_to_key(1) == "coordinator:task:1"


def test_get_task(bespoke_optimization_schema):
    with pytest.raises(IndexError, match="1 was not found"):
        get_task(1)

    create_task(bespoke_optimization_schema)

    task = get_task(1)

    assert isinstance(task, CoordinatorTask)
    assert task.id == "1"


@pytest.mark.parametrize(
    "skip, limit, expected_ids, status",
    [
        (0, 3, [2, 3, 1], None),
        (0, 3, [2, 3, 1], {TaskStatus.waiting, TaskStatus.complete}),
        (0, 2, [2, 3], None),
        (1, 1, [3], None),
        (0, 3, [2, 3], {TaskStatus.waiting}),
        (0, 3, [1], {TaskStatus.complete}),
        (1, 1, [3], {TaskStatus.waiting}),
    ],
)
def test_get_task_ids(skip, limit, expected_ids, status, bespoke_optimization_schema):
    for i in range(3):
        create_task(bespoke_optimization_schema, stages=None if i != 2 else [])

    push_task_status(pop_task_status(TaskStatus.waiting), TaskStatus.complete)

    assert get_task_ids(skip, limit, status=status) == expected_ids


def test_create_task(redis_connection, bespoke_optimization_schema):
    assert redis_connection.get("coordinator:id-counter") is None

    task_id = create_task(bespoke_optimization_schema)
    assert task_id == 1
    assert redis_connection.get("coordinator:id-counter") == b"1"

    assert get_task(task_id).input_schema.id == "1"

    assert get_task_ids(status=TaskStatus.waiting) == [1]


def test_peek_pop_push_task_state(redis_connection, bespoke_optimization_schema):
    for _ in range(2):
        create_task(bespoke_optimization_schema)

    assert peek_task_status(status=TaskStatus.waiting) == 1
    assert pop_task_status(status=TaskStatus.waiting) == 1

    assert peek_task_status(status=TaskStatus.running) is None
    assert pop_task_status(status=TaskStatus.running) is None

    push_task_status(1, TaskStatus.running)
    assert peek_task_status(TaskStatus.running) == 1

    assert get_n_tasks() == 2
    assert get_n_tasks(TaskStatus.waiting) == 1
    assert get_n_tasks(TaskStatus.running) == 1
    assert get_n_tasks(TaskStatus.complete) == 0


def test_save_task(bespoke_optimization_schema):
    task = get_task(create_task(bespoke_optimization_schema))
    assert len(task.pending_stages) == 3

    task.pending_stages = []
    save_task(task)

    updated_task = get_task(task.id)
    assert updated_task.pending_stages == []
