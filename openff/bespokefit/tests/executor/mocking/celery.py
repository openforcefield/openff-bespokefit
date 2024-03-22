"""Utilities for mocking celery tasks."""

from collections import namedtuple
from types import ModuleType
from typing import Any, Optional

from celery.result import AsyncResult


def mock_celery_task(
    worker_module: ModuleType,
    function_name: str,
    monkeypatch,
    task_id: str = "1",
) -> dict[str, Any]:
    """Mock the celery task."""
    submitted_task_kwargs: dict[str, Any] = {}

    def _mock_celery_task_delay(**kwargs):
        submitted_task_kwargs.update(kwargs)
        return namedtuple("MockReturn", "id")(task_id)

    def _mock_celery_task():
        pass

    _mock_celery_task.delay = _mock_celery_task_delay

    monkeypatch.setattr(worker_module, function_name, _mock_celery_task)

    return submitted_task_kwargs


def mock_celery_result(status: str, result: Optional[str] = None) -> AsyncResult:
    """Mock the celery result."""
    result = AsyncResult("1")
    result._cache = {"status": status, "result": result}

    return result
