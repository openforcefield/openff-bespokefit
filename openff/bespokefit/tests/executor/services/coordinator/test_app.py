import pickle

import pytest
import redis
from requests import HTTPError

from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETPageResponse,
    CoordinatorGETResponse,
    CoordinatorPOSTBody,
    CoordinatorPOSTResponse,
    CoordinatorTask,
)
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema


def _mock_task(
    task_id: str, input_schema: BespokeOptimizationSchema, redis_connection: redis.Redis
):

    task = CoordinatorTask(id=task_id, input_schema=input_schema, pending_stages=[])
    task_key = f"coordinator:optimization:{task_id}"

    redis_connection.set(task_key, pickle.dumps(task.dict()))
    redis_connection.zadd("coordinator:optimizations", {task_key: task_id})


@pytest.mark.parametrize(
    "skip, limit, expected_ids, prev_link, next_link",
    [
        (0, 3, {"1", "2", "3"}, None, None),
        (0, 2, {"1", "2"}, None, "/api/v1/tasks?skip=2&limit=2"),
        (1, 1, {"2"}, "/api/v1/tasks?skip=0&limit=1", "/api/v1/tasks?skip=2&limit=1"),
    ],
)
def test_get_optimizations(
    skip,
    limit,
    expected_ids,
    prev_link,
    next_link,
    coordinator_client,
    redis_connection,
    bespoke_optimization_schema,
):

    for task_id in ["1", "2", "3"]:
        _mock_task(task_id, bespoke_optimization_schema, redis_connection)

    redis_connection.set("coordinator:id-counter", 4)

    request = coordinator_client.get(f"/tasks?skip={skip}&limit={limit}")
    request.raise_for_status()

    response = CoordinatorGETPageResponse.parse_raw(request.text)

    assert response.prev == prev_link
    assert response.next == next_link

    assert len(response.contents) == len(expected_ids)
    assert {task.id for task in response.contents} == expected_ids


def test_get_optimization(
    coordinator_client, redis_connection, bespoke_optimization_schema
):

    _mock_task("2", bespoke_optimization_schema, redis_connection)

    request = coordinator_client.get("/tasks/2")
    request.raise_for_status()

    results = CoordinatorGETResponse.parse_raw(request.text)
    assert results.id == "2"
    assert results.self == "/api/v1/tasks/2"

    with pytest.raises(HTTPError, match="404"):
        request = coordinator_client.get("/tasks/1")
        request.raise_for_status()


def test_post_optimization(
    coordinator_client, redis_connection, bespoke_optimization_schema
):
    bespoke_optimization_schema = bespoke_optimization_schema.copy(deep=True)
    bespoke_optimization_schema.smiles = "[Cl:1][H]"
    bespoke_optimization_schema.id = "some-id"

    assert len(redis_connection.keys("*")) == 0

    request = coordinator_client.post(
        "/tasks",
        data=CoordinatorPOSTBody(input_schema=bespoke_optimization_schema).json(),
    )
    request.raise_for_status()

    response = CoordinatorPOSTResponse.parse_raw(request.text)
    assert response.id == "1"
    assert response.self == "/api/v1/tasks/1"

    assert b"coordinator:optimizations" in redis_connection.keys("*")

    key_id_map = redis_connection.zrange("coordinator:optimizations", 0, -1)
    assert len(key_id_map) == 1

    stored_pickled_task = redis_connection.get("coordinator:optimization:1")
    assert stored_pickled_task is not None

    stored_task = CoordinatorTask.parse_obj(pickle.loads(stored_pickled_task))
    assert stored_task.id == "1"
    assert stored_task.input_schema.id == "1"

    assert len(stored_task.pending_stages) == 3
    assert {stage.type for stage in stored_task.pending_stages} == {
        "fragmentation",
        "qc-generation",
        "optimization",
    }

    # make sure the molecule is re-mapped.
    assert stored_task.input_schema.smiles in [
        "[Cl:1][H:2]",
        "[Cl:2][H:1]",
        "[H:1][Cl:2]",
        "[H:2][Cl:1]",
    ]


def test_post_optimization_error(
    coordinator_client, redis_connection, bespoke_optimization_schema
):
    bespoke_optimization_schema = bespoke_optimization_schema.copy(deep=True)
    bespoke_optimization_schema.smiles = "C(F)(Cl)(Br)"

    request = coordinator_client.post(
        "/tasks",
        data=CoordinatorPOSTBody(input_schema=bespoke_optimization_schema).json(),
    )

    assert request.status_code == 400
    assert "molecule could not be understood" in request.text


def test_get_molecule_image(
    coordinator_client, redis_connection, bespoke_optimization_schema
):

    _mock_task("1", bespoke_optimization_schema, redis_connection)

    request = coordinator_client.get("/tasks/1/image")
    request.raise_for_status()

    assert "<svg" in request.text
    assert request.headers["content-type"] == "image/svg+xml"
