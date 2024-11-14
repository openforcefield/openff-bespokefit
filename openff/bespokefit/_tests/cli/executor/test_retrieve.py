import os.path
from contextlib import contextmanager

import pytest
import requests_mock

from openff.bespokefit.cli.executor.retrieve import retrieve_cli
from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETResponse,
    CoordinatorGETStageStatus,
)


@contextmanager
def _mock_coordinator_get(status, results=None):
    settings = current_settings()

    with requests_mock.Mocker() as m:
        mock_href = (
            f"http://127.0.0.1:"
            f"{settings.BEFLOW_GATEWAY_PORT}"
            f"{settings.BEFLOW_API_V1_STR}/"
            f"{settings.BEFLOW_COORDINATOR_PREFIX}/1"
        )
        mock_response = CoordinatorGETResponse(
            id="1",
            self="",
            smiles="CC",
            stages=[
                CoordinatorGETStageStatus(
                    type="fragmentation", status=status, error=None, results=None
                )
            ],
            results=results,
        )
        m.get(
            mock_href,
            text=mock_response.json(by_alias=True),
        )

        yield


def test_retrieve_one_output(runner):
    output = runner.invoke(retrieve_cli, args=["--id", "1"])

    assert output.exit_code == 2
    assert "At least one of the " in output.stdout


@pytest.mark.parametrize(
    "status, expected_message",
    [
        ("waiting", "the bespoke fit is queued"),
        ("running", "the bespoke fit is running"),
        ("errored", "the bespoke fit is errored"),
        ("success", "the bespoke fit is finished"),
    ],
)
def test_retrieve_output(runner, status, expected_message):
    with _mock_coordinator_get(status):
        output = runner.invoke(
            retrieve_cli, args=["--id", "1", "--output", "output.json"]
        )

    assert os.path.isfile("output.json")

    assert output.exit_code == 0
    assert expected_message in output.stdout


@pytest.mark.parametrize(
    "status, expected_message, should_exist",
    [
        ("running", "the bespoke fit is still running and so no force field", False),
        ("errored", "the bespoke fit failed and so no force field", False),
        ("success", "the bespoke force field has been saved to", True),
    ],
)
def test_retrieve_force_field(
    runner, status, expected_message, should_exist, bespoke_optimization_results
):
    with _mock_coordinator_get(
        status, results=None if status != "success" else bespoke_optimization_results
    ):
        output = runner.invoke(
            retrieve_cli, args=["--id", "1", "--force-field", "output.offxml"]
        )

    assert os.path.isfile("output.offxml") == should_exist
    assert output.exit_code == 0
    assert expected_message in output.stdout


def test_retrieve_errored(runner):
    output = runner.invoke(retrieve_cli, args=["--id", "1", "--output", "output.json"])

    assert output.exit_code == 2
    assert "failed to connect to the" in output.stdout
