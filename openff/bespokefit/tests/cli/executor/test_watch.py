import requests_mock

from openff.bespokefit.cli.executor.watch import watch_cli
from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETResponse,
    CoordinatorGETStageStatus,
)


def test_watch(runner):

    with requests_mock.Mocker() as m:

        mock_href = (
            f"http://127.0.0.1:"
            f"{settings.BEFLOW_GATEWAY_PORT}"
            f"{settings.BEFLOW_API_V1_STR}/"
            f"{settings.BEFLOW_COORDINATOR_PREFIX}/1"
        )

        mock_response = CoordinatorGETResponse(
            id="1",
            self=mock_href,
            stages=[
                CoordinatorGETStageStatus(
                    type="fragmentation", status="success", error=None, results=None
                )
            ],
        )
        m.get(
            mock_href,
            text=mock_response.json(),
        )

        output = runner.invoke(watch_cli, args=["--id", "1"])

        assert output.exit_code == 0
        assert "fragmentation successful" in output.stdout
