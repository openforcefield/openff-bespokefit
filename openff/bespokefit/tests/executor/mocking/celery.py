from collections import namedtuple
from types import ModuleType
from typing import Any, Dict, Optional

from celery.result import AsyncResult


def mock_celery_task(
    worker_module: ModuleType, function_name: str, monkeypatch
) -> Dict[str, Any]:

    submitted_task_kwargs: Dict[str, Any] = {}

    def _mock_celery_task_delay(**kwargs):

        submitted_task_kwargs.update(kwargs)
        return namedtuple("MockReturn", "id")("1")

    def _mock_celery_task():
        pass

    _mock_celery_task.delay = _mock_celery_task_delay

    monkeypatch.setattr(worker_module, function_name, _mock_celery_task)

    return submitted_task_kwargs


def mock_celery_result(status: str, result: Optional[str] = None) -> AsyncResult:

    result = AsyncResult("1")
    result._cache = {"status": status, "result": result}

    return result
