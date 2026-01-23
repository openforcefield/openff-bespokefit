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
    remove_task_status,
    save_task,
    snapshot_task_status,
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


def test_snapshot_task_status_empty(redis_connection):
    """Test snapshot_task_status returns empty list when no tasks in queue."""
    snapshot = snapshot_task_status(TaskStatus.waiting)
    assert snapshot == []

    snapshot = snapshot_task_status(TaskStatus.running)
    assert snapshot == []


def test_snapshot_task_status_single(redis_connection, bespoke_optimization_schema):
    """Test snapshot_task_status returns single task correctly."""
    task_id = create_task(bespoke_optimization_schema)

    snapshot = snapshot_task_status(TaskStatus.waiting)
    assert snapshot == [1]
    assert isinstance(snapshot[0], int)


def test_snapshot_task_status_multiple(redis_connection, bespoke_optimization_schema):
    """Test snapshot_task_status returns multiple tasks in correct order."""
    # Create 3 tasks
    for _ in range(3):
        create_task(bespoke_optimization_schema)

    # All should be in waiting queue
    snapshot = snapshot_task_status(TaskStatus.waiting)
    assert snapshot == [1, 2, 3]

    # Move some to running
    push_task_status(pop_task_status(TaskStatus.waiting), TaskStatus.running)
    push_task_status(pop_task_status(TaskStatus.waiting), TaskStatus.running)

    # Check both queues
    waiting_snapshot = snapshot_task_status(TaskStatus.waiting)
    running_snapshot = snapshot_task_status(TaskStatus.running)

    assert waiting_snapshot == [3]
    assert running_snapshot == [1, 2]


def test_snapshot_task_status_independence(redis_connection, bespoke_optimization_schema):
    """Test that snapshot is independent of queue changes."""
    # Create 2 tasks
    for _ in range(2):
        create_task(bespoke_optimization_schema)

    # Take snapshot
    snapshot = snapshot_task_status(TaskStatus.waiting)
    assert snapshot == [1, 2]

    # Modify queue after snapshot
    pop_task_status(TaskStatus.waiting)

    # Snapshot should be unchanged
    assert snapshot == [1, 2]

    # But new snapshot should reflect changes
    new_snapshot = snapshot_task_status(TaskStatus.waiting)
    assert new_snapshot == [2]


def test_remove_task_status_present(redis_connection, bespoke_optimization_schema):
    """Test remove_task_status successfully removes a present task."""
    # Create and queue 3 tasks
    for _ in range(3):
        task_id = create_task(bespoke_optimization_schema)
        push_task_status(pop_task_status(TaskStatus.waiting), TaskStatus.running)

    # Verify all in running queue
    assert get_n_tasks(TaskStatus.running) == 3
    snapshot = snapshot_task_status(TaskStatus.running)
    assert snapshot == [1, 2, 3]

    # Remove task 2
    removed_count = remove_task_status(2, TaskStatus.running)

    # Should return 1 (one task removed)
    assert removed_count == 1

    # Task should be gone from queue
    snapshot = snapshot_task_status(TaskStatus.running)
    assert snapshot == [1, 3]
    assert get_n_tasks(TaskStatus.running) == 2


def test_remove_task_status_absent(redis_connection, bespoke_optimization_schema):
    """Test remove_task_status returns 0 when task not in queue."""
    # Create task but leave in waiting queue
    create_task(bespoke_optimization_schema)

    # Try to remove from running queue (where it doesn't exist)
    removed_count = remove_task_status(1, TaskStatus.running)

    # Should return 0 (no tasks removed)
    assert removed_count == 0

    # Task should still be in waiting queue
    assert get_n_tasks(TaskStatus.waiting) == 1


def test_remove_task_status_nonexistent_id(redis_connection, bespoke_optimization_schema):
    """Test remove_task_status with task ID that doesn't exist anywhere."""
    # Create one task
    create_task(bespoke_optimization_schema)

    # Try to remove task 999 which doesn't exist
    removed_count = remove_task_status(999, TaskStatus.waiting)

    # Should return 0
    assert removed_count == 0

    # Original task should be unaffected
    assert get_n_tasks(TaskStatus.waiting) == 1


def test_remove_task_status_head(redis_connection, bespoke_optimization_schema):
    """Test remove_task_status can remove head of queue."""
    # Create 3 tasks
    for _ in range(3):
        create_task(bespoke_optimization_schema)

    # Remove first task (head)
    removed_count = remove_task_status(1, TaskStatus.waiting)

    assert removed_count == 1
    snapshot = snapshot_task_status(TaskStatus.waiting)
    assert snapshot == [2, 3]


def test_remove_task_status_tail(redis_connection, bespoke_optimization_schema):
    """Test remove_task_status can remove tail of queue."""
    # Create 3 tasks
    for _ in range(3):
        create_task(bespoke_optimization_schema)

    # Remove last task (tail)
    removed_count = remove_task_status(3, TaskStatus.waiting)

    assert removed_count == 1
    snapshot = snapshot_task_status(TaskStatus.waiting)
    assert snapshot == [1, 2]


def test_remove_task_status_middle(redis_connection, bespoke_optimization_schema):
    """Test remove_task_status can remove middle element."""
    # Create 3 tasks
    for _ in range(3):
        create_task(bespoke_optimization_schema)

    # Remove middle task
    removed_count = remove_task_status(2, TaskStatus.waiting)

    assert removed_count == 1
    snapshot = snapshot_task_status(TaskStatus.waiting)
    assert snapshot == [1, 3]


@pytest.mark.parametrize("status", [TaskStatus.waiting, TaskStatus.running, TaskStatus.complete])
def test_remove_task_status_all_statuses(redis_connection, bespoke_optimization_schema, status):
    """Test remove_task_status works with all task statuses."""
    # Create task and move to target status
    task_id = create_task(bespoke_optimization_schema)

    if status == TaskStatus.running:
        push_task_status(pop_task_status(TaskStatus.waiting), TaskStatus.running)
    elif status == TaskStatus.complete:
        push_task_status(pop_task_status(TaskStatus.waiting), TaskStatus.complete)

    # Remove from target status
    removed_count = remove_task_status(task_id, status)

    assert removed_count == 1
    assert get_n_tasks(status) == 0
