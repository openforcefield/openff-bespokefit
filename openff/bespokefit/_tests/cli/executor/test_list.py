import pytest
import requests_mock

from openff.bespokefit.cli.executor.list import list_cli
from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETPageResponse,
    CoordinatorGETResponse,
)
from openff.bespokefit.executor.services.models import Link


@pytest.mark.parametrize(
    "n_results, expected_message",
    [(0, "No optimizations were found"), (3, "The following optimizations were found")],
)
def test_list_cli(n_results, expected_message, runner):
    settings = current_settings()

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
        for i in range(1, n_results + 1):
            mock_response = CoordinatorGETResponse(
                self="self-page",
                id=str(i),
                smiles="[C:1]([H:2])([H:3])=[C:4]([H:5])[H:6]",
                stages=[],
            )
            m.get(
                (
                    f"http://127.0.0.1:"
                    f"{settings.BEFLOW_GATEWAY_PORT}"
                    f"{settings.BEFLOW_API_V1_STR}/"
                    f"{settings.BEFLOW_COORDINATOR_PREFIX}/{i}"
                ),
                text=mock_response.json(by_alias=True),
            )

        output = runner.invoke(list_cli)
        assert output.exit_code == 0

    assert expected_message in output.stdout
