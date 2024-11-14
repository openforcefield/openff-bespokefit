import os

import requests_mock
from openff.toolkit.typing.engines.smirnoff import ForceField

from openff.bespokefit.cli.combine import combine_cli
from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETResponse,
    CoordinatorGETStageStatus,
)


def test_combine_no_args(runner):
    """
    Make sure an error is raised when we supply no args
    """

    output = runner.invoke(combine_cli, args=["--output", "my_ff.offxml"])

    assert output.exit_code == 2
    assert "At least one of the" in output.stdout


def test_combine_local_and_tasks(tmpdir, runner, bespoke_optimization_results):
    """
    Make sure local force field files can be combined with task force fields
    """

    # make some local files to work with
    for ff_name in ["openff-1.0.0.offxml", "openff-2.2.0.offxml"]:
        ForceField(ff_name).to_file(ff_name)

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
                    type="optimization", status="success", error=None, results=None
                )
            ],
            results=bespoke_optimization_results,
        )
        m.get(mock_href, text=mock_response.json(by_alias=True))

        output = runner.invoke(
            combine_cli,
            args=[
                "--output",
                "my_ff.offxml",
                "--ff",
                "openff-2.2.0.offxml",
                "--ff",
                "openff-1.0.0.offxml",
                "--id",
                "1",
            ],
        )

    assert os.path.isfile("my_ff.offxml")
    assert output.exit_code == 0
    assert "The combined force field has been saved to" in output.stdout
