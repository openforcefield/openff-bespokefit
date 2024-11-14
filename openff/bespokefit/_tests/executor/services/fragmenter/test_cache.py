from openff.fragmenter.fragment import WBOFragmenter

from openff.bespokefit._tests.executor.mocking.celery import mock_celery_task
from openff.bespokefit.executor.services.fragmenter import worker
from openff.bespokefit.executor.services.fragmenter.cache import (
    cached_fragmentation_task,
)
from openff.bespokefit.executor.services.fragmenter.models import FragmenterPOSTBody


def test_cached_fragmentation_task(fragmenter_client, redis_connection, monkeypatch):
    """
    Make sure fragmenter results are cached and can be reused.
    """

    mock_celery_task(worker, "fragment", monkeypatch, "task-1")
    # build a fake task
    task = FragmenterPOSTBody(
        cmiles="[H:4][C:2]([H:5])([O:3][H:6])[Br:1]",
        fragmenter=WBOFragmenter(),
        target_bond_smarts=["[!#1]~[!$(*#*)&!D1:1]-,=;!@[!$(*#*)&!D1:2]~[!#1]"],
    )
    task_id = cached_fragmentation_task(task=task, redis_connection=redis_connection)

    # modify the worker to produce the next task id
    mock_celery_task(worker, "fragment", monkeypatch, "task-2")

    # submit the task again and make sure it has the same id as the first task
    assert (
        cached_fragmentation_task(task=task, redis_connection=redis_connection)
        == task_id
        == "task-1"
    )

    # modify the task and submit again
    task.fragmenter.keep_non_rotor_ring_substituents = True
    assert (
        cached_fragmentation_task(task=task, redis_connection=redis_connection)
        == "task-2"
    )
