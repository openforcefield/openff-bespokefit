from celery.result import AsyncResult
from openff.fragmenter.fragment import FragmentationResult, PfizerFragmenter

from openff.bespokefit.executor.services.fragmenter import worker
from openff.bespokefit.executor.services.fragmenter.models import (
    FragmenterGETResponse,
    FragmenterPOSTBody,
    FragmenterPOSTResponse,
)
from openff.bespokefit.tests.executor.mocking.celery import mock_celery_task


def test_get_fragment(fragmenter_client, redis_connection, monkeypatch):

    mock_fragmentation_result = FragmentationResult(
        parent_smiles="[Ar:1]", fragments=[], provenance={"version": "mock"}
    )

    monkeypatch.setattr(
        AsyncResult,
        "_get_task_meta",
        lambda self: {"status": "SUCCESS", "result": mock_fragmentation_result.json()},
    )

    request = fragmenter_client.get("/fragmenter/1")
    request.raise_for_status()

    result = FragmenterGETResponse.parse_raw(request.text)

    assert result.fragmentation_status == "success"
    assert result.fragmentation_result is not None
    assert result.fragmentation_id == "1"

    assert (
        result.fragmentation_result.parent_smiles
        == mock_fragmentation_result.parent_smiles
    )
    assert (
        result.fragmentation_result.provenance == mock_fragmentation_result.provenance
    )


def test_post_fragment(fragmenter_client, redis_connection, monkeypatch):

    submitted_task_kwargs = mock_celery_task(worker, "fragment", monkeypatch)

    request = fragmenter_client.post(
        "/fragmenter",
        data=FragmenterPOSTBody(
            cmiles="[CH2:1]=[CH2:2]",
            fragmenter=PfizerFragmenter(),
            target_bond_smarts=["[#6:1]-[#6:2]"],
        ).json(),
    )
    request.raise_for_status()

    assert submitted_task_kwargs is not None

    assert submitted_task_kwargs["cmiles"] == "[CH2:1]=[CH2:2]"
    assert submitted_task_kwargs["target_bond_smarts"] == ["[#6:1]-[#6:2]"]

    result = FragmenterPOSTResponse.parse_raw(request.text)
    assert result.fragmentation_id == "1"
