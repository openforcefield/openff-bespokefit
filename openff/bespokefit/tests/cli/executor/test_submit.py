import os.path

import numpy
import pytest
import requests_mock
import rich
from openff.toolkit.topology import Molecule, Topology
from openmm import unit

from openff.bespokefit.cli.executor.submit import _submit, _to_input_schema, submit_cli
from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorPOSTResponse,
)
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema


@pytest.mark.parametrize(
    "spec_name, spec_file_name, expected_message, output_is_none",
    [
        (None, None, "The `spec` and `spec-file` arguments", True),
        ("a", "b", "The `spec` and `spec-file` arguments", True),
        ("debug", None, "", False),
    ],
)
def test_to_input_schema_mutual_exclusive_args(
    spec_name, spec_file_name, expected_message, output_is_none
):

    console = rich.get_console()

    with console.capture() as capture:

        input_schema = _to_input_schema(
            console,
            Molecule.from_smiles("CC"),
            force_field_path="openff-2.0.0.offxml",
            spec_name=spec_name,
            spec_file_name=spec_file_name,
        )

    if len(expected_message) > 0:
        assert expected_message in capture.get()

    assert (input_schema is None) == output_is_none


def test_to_input_schema():

    input_schema = _to_input_schema(
        rich.get_console(),
        Molecule.from_smiles("CC"),
        force_field_path="openff-1.2.1.offxml",
        spec_name="debug",
        spec_file_name=None,
    )

    assert isinstance(input_schema, BespokeOptimizationSchema)
    assert input_schema.id == "bespoke_task_0"


def test_submit_multi_molecule(tmpdir):

    console = rich.get_console()

    input_file_path = os.path.join(tmpdir, "mol.pdb")

    molecules = [Molecule.from_smiles(smiles) for smiles in ("ClCl", "BrBr")]
    Topology.from_molecules(molecules).to_file(
        input_file_path, positions=numpy.zeros((4, 3)) * unit.angstrom
    )

    with console.capture() as capture:

        response = _submit(
            console,
            input_file_path=input_file_path,
            force_field_path="openff-2.0.0.offxml",
            spec_name="debug",
            spec_file_name=None,
        )

    assert response is None
    assert "only one molecule can currently" in capture.get()


def test_submit_invalid_schema(tmpdir):
    """Make sure to schema failures are cleanly handled."""

    input_file_path = os.path.join(tmpdir, "mol.sdf")
    Molecule.from_smiles("C").to_file(input_file_path, "SDF")

    response = _submit(
        rich.get_console(),
        input_file_path=input_file_path,
        force_field_path="openff-2.0.0.offxml",
        spec_name=None,
        spec_file_name=None,
    )

    assert response is None


def test_submit(tmpdir):
    """Make sure to schema failures are cleanly handled."""

    input_file_path = os.path.join(tmpdir, "mol.sdf")
    Molecule.from_smiles("CC").to_file(input_file_path, "SDF")

    with requests_mock.Mocker() as m:

        mock_href = (
            f"http://127.0.0.1:"
            f"{settings.BEFLOW_GATEWAY_PORT}"
            f"{settings.BEFLOW_API_V1_STR}/"
            f"{settings.BEFLOW_COORDINATOR_PREFIX}"
        )
        m.post(mock_href, text=CoordinatorPOSTResponse(self="", id="1").json())

        response = _submit(
            rich.get_console(),
            input_file_path=input_file_path,
            force_field_path="openff-2.0.0.offxml",
            spec_name="debug",
            spec_file_name=None,
        )

    assert isinstance(response, CoordinatorPOSTResponse)
    assert response.id == "1"


def test_submit_cli(runner, tmpdir):
    """Make sure to schema failures are cleanly handled."""

    input_file_path = os.path.join(tmpdir, "mol.sdf")
    Molecule.from_smiles("CC").to_file(input_file_path, "SDF")

    with requests_mock.Mocker() as m:

        mock_href = (
            f"http://127.0.0.1:"
            f"{settings.BEFLOW_GATEWAY_PORT}"
            f"{settings.BEFLOW_API_V1_STR}/"
            f"{settings.BEFLOW_COORDINATOR_PREFIX}"
        )
        m.post(mock_href, text=CoordinatorPOSTResponse(self="", id="1").json())

        output = runner.invoke(
            submit_cli, args=["--input", input_file_path, "--spec", "debug"]
        )

    assert output.exit_code == 0
    assert "workflow submitted: id=1" in output.output
