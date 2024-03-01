import pytest
from httpx import HTTPStatusError

from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETPageResponse,
    CoordinatorGETResponse,
    CoordinatorPOSTBody,
    CoordinatorPOSTResponse,
)
from openff.bespokefit.executor.services.coordinator.storage import (
    TaskStatus,
    create_task,
    get_task,
    pop_task_status,
    push_task_status,
)


@pytest.mark.parametrize(
    "skip, limit, status, expected_ids, prev_link, next_link",
    [
        (0, 3, None, {"2", "3", "1"}, None, None),
        (
            0,
            2,
            None,
            {
                "2",
                "3",
            },
            None,
            "/api/v1/tasks?skip=2&limit=2",
        ),
        (
            1,
            1,
            None,
            {"3"},
            "/api/v1/tasks?skip=0&limit=1",
            "/api/v1/tasks?skip=2&limit=1",
        ),
        (
            1,
            1,
            TaskStatus.waiting,
            {"3"},
            "/api/v1/tasks?skip=0&limit=1&status=waiting",
            None,
        ),
        (0, 1, TaskStatus.complete, {"1"}, None, None),
    ],
)
def test_get_optimizations(
    skip,
    limit,
    status,
    expected_ids,
    prev_link,
    next_link,
    coordinator_client,
    bespoke_optimization_schema,
):
    for i in range(3):
        create_task(bespoke_optimization_schema, stages=None if i != 2 else [])

    push_task_status(pop_task_status(TaskStatus.waiting), TaskStatus.complete)

    status_url = "" if status is None else f"&status={status.value}"

    request = coordinator_client.get(f"/tasks?skip={skip}&limit={limit}{status_url}")
    request.raise_for_status()

    response = CoordinatorGETPageResponse.parse_raw(request.text)

    assert response.prev == prev_link
    assert response.next == next_link

    assert len(response.contents) == len(expected_ids)
    assert {task.id for task in response.contents} == expected_ids


def test_get_optimization(coordinator_client, bespoke_optimization_schema):
    for _ in range(2):
        create_task(bespoke_optimization_schema)

    request = coordinator_client.get("/tasks/2")
    request.raise_for_status()

    results = CoordinatorGETResponse.parse_raw(request.text)
    assert results.id == "2"
    assert results.self == "/api/v1/tasks/2"

    with pytest.raises(HTTPStatusError, match="404"):
        request = coordinator_client.get("/tasks/3")
        request.raise_for_status()


def test_post_optimization(coordinator_client, bespoke_optimization_schema):
    bespoke_optimization_schema = bespoke_optimization_schema.copy(deep=True)
    bespoke_optimization_schema.smiles = "[Cl:1][H]"
    bespoke_optimization_schema.id = "some-id"

    with pytest.raises(IndexError):
        get_task(1)

    request = coordinator_client.post(
        "/tasks",
        data=CoordinatorPOSTBody(input_schema=bespoke_optimization_schema).json(),
    )
    request.raise_for_status()

    response = CoordinatorPOSTResponse.parse_raw(request.text)
    assert response.id == "1"
    assert response.self == "/api/v1/tasks/1"

    stored_task = get_task(1)
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


def test_post_optimization_error(coordinator_client, bespoke_optimization_schema):
    bespoke_optimization_schema = bespoke_optimization_schema.copy(deep=True)
    bespoke_optimization_schema.smiles = "C(F)(Cl)(Br)"

    request = coordinator_client.post(
        "/tasks",
        data=CoordinatorPOSTBody(input_schema=bespoke_optimization_schema).json(),
    )

    assert request.status_code == 400
    assert "molecule could not be understood" in request.text


def test_get_molecule_image(coordinator_client, bespoke_optimization_schema):
    create_task(bespoke_optimization_schema)

    request = coordinator_client.get("/tasks/1/image")
    request.raise_for_status()

    assert "<svg" in request.text
    assert request.headers["content-type"] == "image/svg+xml"
