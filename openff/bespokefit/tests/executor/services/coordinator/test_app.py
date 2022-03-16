import pytest
from requests import HTTPError

from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETPageResponse,
    CoordinatorGETResponse,
    CoordinatorPOSTBody,
    CoordinatorPOSTResponse,
)
from openff.bespokefit.executor.services.coordinator.storage import (
    create_task,
    get_task,
)


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
    bespoke_optimization_schema,
):

    for _ in range(3):
        create_task(bespoke_optimization_schema)

    request = coordinator_client.get(f"/tasks?skip={skip}&limit={limit}")
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

    with pytest.raises(HTTPError, match="404"):
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
