from celery.result import AsyncResult
from openff.fragmenter.fragment import Fragment, FragmentationResult, PfizerFragmenter

from openff.bespokefit.executor.services.fragmenter import worker
from openff.bespokefit.executor.services.fragmenter.models import (
    FragmenterGETResponse,
    FragmenterPOSTBody,
    FragmenterPOSTResponse,
)
from openff.bespokefit.executor.utilities.depiction import IMAGE_UNAVAILABLE_SVG
from openff.bespokefit.tests.executor.mocking.celery import mock_celery_task


def _mock_fragment(monkeypatch, status: str = "SUCCESS") -> FragmentationResult:
    mock_fragmentation_result = FragmentationResult(
        parent_smiles="[H:1][C:2]#[C:3][H:4]",
        fragments=[
            Fragment(smiles="[H:1][C:2]#[C:3][H:4]", bond_indices=(2, 3)),
            Fragment(smiles="[H:1][C:2]#[C:3][H:4]", bond_indices=(3, 4)),
        ],
        provenance={"version": "mock"},
    )

    monkeypatch.setattr(
        AsyncResult,
        "_get_task_meta",
        lambda self: {"status": status, "result": mock_fragmentation_result.json()},
    )

    return mock_fragmentation_result


def test_get_fragment(fragmenter_client, monkeypatch):
    mock_fragmentation_result = _mock_fragment(monkeypatch)

    request = fragmenter_client.get("/fragmentations/1")
    request.raise_for_status()

    result = FragmenterGETResponse.parse_raw(request.text)

    assert result.status == "success"
    assert result.result is not None
    assert result.id == "1"
    assert result.self == "/api/v1/fragmentations/1"

    assert result.result.parent_smiles == mock_fragmentation_result.parent_smiles
    assert result.result.provenance == mock_fragmentation_result.provenance


def test_post_fragment(fragmenter_client, redis_connection, monkeypatch):
    submitted_task_kwargs = mock_celery_task(worker, "fragment", monkeypatch)

    request = fragmenter_client.post(
        "/fragmentations",
        data=FragmenterPOSTBody(
            cmiles="[H:3][C:1](=[C:2]([H:5])[H:6])[H:4]",
            fragmenter=PfizerFragmenter(),
            target_bond_smarts=["[#6:1]-[#6:2]"],
        ).json(),
    )
    request.raise_for_status()

    assert submitted_task_kwargs is not None

    assert submitted_task_kwargs["cmiles"] == "[H:3][C:1](=[C:2]([H:5])[H:6])[H:4]"
    assert submitted_task_kwargs["target_bond_smarts"] == ["[#6:1]-[#6:2]"]

    result = FragmenterPOSTResponse.parse_raw(request.text)
    assert result.id == "1"
    assert result.self == "/api/v1/fragmentations/1"


def test_get_molecule_image(fragmenter_client, monkeypatch):
    _mock_fragment(monkeypatch)

    request = fragmenter_client.get("/fragmentations/1/fragment/0/image")
    request.raise_for_status()

    assert "<svg" in request.text
    assert request.headers["content-type"] == "image/svg+xml"


def test_get_molecule_image_pending(fragmenter_client, monkeypatch):
    _mock_fragment(monkeypatch, "PENDING")

    request = fragmenter_client.get("/fragmentations/1/fragment/0/image")
    request.raise_for_status()

    assert request.text == IMAGE_UNAVAILABLE_SVG
    assert request.headers["content-type"] == "image/svg+xml"


def test_get_molecule_image_bad_id(fragmenter_client, monkeypatch):
    _mock_fragment(monkeypatch)

    request = fragmenter_client.get("/fragmentations/1/fragment/100/image")
    request.raise_for_status()

    assert request.text == IMAGE_UNAVAILABLE_SVG
    assert request.headers["content-type"] == "image/svg+xml"
