import os

import requests_mock
from openff.toolkit.topology import Molecule

from openff.bespokefit.cli.executor.run import run_cli
from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETResponse,
    CoordinatorGETStageStatus,
    CoordinatorPOSTResponse,
)


def test_run(runner, tmpdir):
    """Make sure to schema failures are cleanly handled."""

    input_file_path = os.path.join(tmpdir, "mol.sdf")
    Molecule.from_smiles("CC").to_file(input_file_path, "SDF")

    settings = current_settings()

    with requests_mock.Mocker() as m:

        m.post(
            (
                f"http://127.0.0.1:"
                f"{settings.BEFLOW_GATEWAY_PORT}"
                f"{settings.BEFLOW_API_V1_STR}/"
                f"{settings.BEFLOW_COORDINATOR_PREFIX}"
            ),
            text=CoordinatorPOSTResponse(self="", id="1").json(),
        )
        m.get("http://127.0.0.1:8000/api/v1", text="")
        m.get(
            (
                f"http://127.0.0.1:"
                f"{settings.BEFLOW_GATEWAY_PORT}"
                f"{settings.BEFLOW_API_V1_STR}/"
                f"{settings.BEFLOW_COORDINATOR_PREFIX}/1"
            ),
            text=CoordinatorGETResponse(
                id="1",
                self="",
                smiles="CC",
                stages=[
                    CoordinatorGETStageStatus(
                        type="fragmentation", status="success", error=None, results=None
                    )
                ],
            ).json(by_alias=True),
        )

        output = runner.invoke(
            run_cli,
            args=[
                "--file",
                input_file_path,
                "--workflow",
                "debug",
                "--directory",
                "mock-directory",
                "--n-fragmenter-workers",
                0,
                "--n-qc-compute-workers",
                0,
                "--n-optimizer-workers",
                0,
                "--no-launch-redis",
            ],
        )

    assert output.exit_code == 0
    assert "the following workflows were submitted" in output.output
