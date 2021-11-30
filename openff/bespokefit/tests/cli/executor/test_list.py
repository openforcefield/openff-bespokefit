import pytest
import requests_mock

from openff.bespokefit.cli.executor.list import list_cli
from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETPageResponse,
)
from openff.bespokefit.executor.services.models import Link


@pytest.mark.parametrize(
    "n_results, expected_message",
    [(0, "No optimizations were found"), (3, "The following optimizations were found")],
)
def test_list_cli(n_results, expected_message, runner):

    with requests_mock.Mocker() as m:

        mock_response = CoordinatorGETPageResponse(
            self="self-page",
            contents=[
                Link(id=f"{i}", self=f"self-{i}") for i in range(1, 1 + n_results)
            ],
        )

        m.get(
            (
                f"http://127.0.0.1:"
                f"{settings.BEFLOW_GATEWAY_PORT}"
                f"{settings.BEFLOW_API_V1_STR}/"
                f"{settings.BEFLOW_COORDINATOR_PREFIX}"
            ),
            text=mock_response.json(),
        )

        output = runner.invoke(list_cli)
        assert output.exit_code == 0

    assert expected_message in output.stdout
