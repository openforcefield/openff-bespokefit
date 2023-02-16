import asyncio
import logging
import time

import redis

from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.services.coordinator.storage import (
    TaskStatus,
    get_n_tasks,
    get_task,
    peek_task_status,
    pop_task_status,
    push_task_status,
    save_task,
)

_logger = logging.getLogger(__name__)


async def _process_task(task_id: int) -> bool:
    task = get_task(task_id)
    task_status = task.status

    if task.status == "success" or task.status == "errored":
        return True

    if task.running_stage is None:
        task.running_stage = task.pending_stages.pop(0)
        await task.running_stage.enter(task)

    stage_status = task.running_stage.status
    await task.running_stage.update()

    task_state_message = f"[task id={task_id}] transitioned from {{0}} -> {{1}}"

    if task.status != task_status and task_status == "waiting":
        print(task_state_message.format(task_status, task.status), flush=True)

    if stage_status != task.running_stage.status:
        print(
            f"[task id={task_id}] {task.running_stage.type} transitioned from "
            f"{stage_status} -> {task.running_stage.status}",
            flush=True,
        )

    if task.running_stage.status in {"success", "errored"}:
        task.completed_stages.append(task.running_stage)
        task.running_stage = None

    if task.status != task_status and task_status != "waiting":
        print(task_state_message.format(task_status, task.status), flush=True)

    save_task(task)
    return False


async def cycle():  # pragma: no cover
    settings = current_settings()
    n_connection_errors = 0

    while True:
        sleep_time = settings.BEFLOW_COORDINATOR_MAX_UPDATE_INTERVAL

        try:
            start_time = time.perf_counter()

            # First update any running tasks, pushing them to the 'complete' queue if
            # they have finished, so as to figure out how many new tasks can be moved
            # from running to waiting.

            task_id = peek_task_status(TaskStatus.running)
            processed_task_ids = set()

            while task_id is not None:
                if task_id in processed_task_ids:
                    break

                has_finished = await _process_task(task_id)
                # Needed to let other async threads run even if there are hundreds of
                # tasks running
                await asyncio.sleep(0.0)

                push_task_status(
                    pop_task_status(TaskStatus.running),
                    TaskStatus.running if not has_finished else TaskStatus.complete,
                )

                processed_task_ids.add(task_id)

                task_id = peek_task_status(TaskStatus.running)

            n_running_tasks = get_n_tasks(TaskStatus.running)
            n_tasks_to_queue = min(
                settings.BEFLOW_COORDINATOR_MAX_RUNNING_TASKS - n_running_tasks,
                get_n_tasks(TaskStatus.waiting),
            )

            for _ in range(n_tasks_to_queue):
                push_task_status(
                    pop_task_status(TaskStatus.waiting), TaskStatus.running
                )

            n_connection_errors = 0

            # Make sure we don't cycle too often
            sleep_time = max(sleep_time - (time.perf_counter() - start_time), 0.0)

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

        await asyncio.sleep(sleep_time)
