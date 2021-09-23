import asyncio
import logging
import pickle

import redis

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.coordinator.models import CoordinatorTask

_logger = logging.getLogger(__name__)

redis_connection = redis.Redis(
    host=settings.BEFLOW_REDIS_ADDRESS,
    port=settings.BEFLOW_REDIS_PORT,
    db=settings.BEFLOW_REDIS_DB,
)


async def _cycle():

    task_ids = redis_connection.zrange("coordinator:optimizations", 0, -1)

    for task_id in task_ids:

        task_pickle = redis_connection.get(task_id)
        task = CoordinatorTask.parse_obj(pickle.loads(task_pickle))

        task_status = task.status

        if task.status == "success" or task.status == "errored":
            continue

        if task.running_stage is None:
            task.running_stage = task.pending_stages.pop(0)
            await task.running_stage.enter(task)

            print(f"[task id={task_id}] starting {task.running_stage.type} stage")

        stage_status = task.running_stage.status
        await task.running_stage.update()

        if stage_status != task.running_stage.status:
            print(
                f"[task id={task_id}] {task.running_stage.type} transitioned from "
                f"{stage_status} -> {task.running_stage.status}"
            )

        if task.running_stage.status in {"success", "errored"}:
            task.completed_stages.append(task.running_stage)
            task.running_stage = None

        if task.status != task_status:
            print(
                f"[task id={task_id}] transitioned from {task_status} -> "
                f"{task.status}"
            )

        redis_connection.set(task_id, pickle.dumps(task.dict()))


async def cycle():  # pragma: no cover

    n_connection_errors = 0

    while True:

        try:

            await _cycle()
            n_connection_errors = 0

        except (KeyboardInterrupt, asyncio.CancelledError):

            break

        except (
            ConnectionError,
            redis.exceptions.ConnectionError,
            redis.exceptions.BusyLoadingError,
        ) as e:

            n_connection_errors += 1

            if n_connection_errors >= 3:
                raise e

            if isinstance(e, redis.exceptions.RedisError):

                _logger.warning(
                    f"Failed to connect to Redis - {3 - n_connection_errors} attempts "
                    f"remaining."
                )

        await asyncio.sleep(5)
