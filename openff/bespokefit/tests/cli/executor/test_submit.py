import json
import os.path

import click.exceptions
import numpy
import pytest
import requests_mock
import rich
from openff.toolkit.topology import Molecule, Topology
from openff.utilities import get_data_file_path
from openmm import unit

from openff.bespokefit.cli.executor.submit import (
    _submit,
    _submit_cli,
    _to_input_schema,
    submit_cli,
)
from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorPOSTResponse,
)
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.tests import does_not_raise
from openff.bespokefit.workflows import BespokeWorkflowFactory


def test_default_workflow_up_to_date():

    current_default_workflow = BespokeWorkflowFactory().json(sort_keys=True, indent=2)

    with open(
        get_data_file_path(os.path.join("schemas", "default.json"), "openff.bespokefit")
    ) as file:

        default_workflow_from_file = json.dumps(
            json.load(file), sort_keys=True, indent=2
        )

    assert current_default_workflow == default_workflow_from_file

    # with open(
    #     get_data_file_path(
    #         os.path.join("schemas", "default.json"), "openff.bespokefit"
    #     ),
    #     "w",
    # ) as file:
    #     file.write(BespokeWorkflowFactory().json(indent=2))


@pytest.mark.parametrize(
    "workflow_name, workflow_file_name, expected_message, expected_raises, output_is_none",
    [
        (
            None,
            None,
            "The `--workflow` and `--workflow-file` arguments",
            pytest.raises(click.exceptions.Exit),
            True,
        ),
        (
            "a",
            "b",
            "The `--workflow` and `--workflow-file` arguments",
            pytest.raises(click.exceptions.Exit),
            True,
        ),
        ("debug", None, "", does_not_raise(), False),
    ],
)
def test_to_input_schema_mutual_exclusive_args(
    workflow_name, workflow_file_name, expected_message, expected_raises, output_is_none
):

    console = rich.get_console()

    input_schema = None

    with console.capture() as capture:
        with expected_raises:

            input_schema = _to_input_schema(
                console,
                Molecule.from_smiles("CC"),
                force_field_path="openff-2.0.0.offxml",
                target_torsion_smirks=tuple(),
                workflow_name=workflow_name,
                workflow_file_name=workflow_file_name,
            )

    if len(expected_message) > 0:
        assert expected_message in capture.get()

    assert (input_schema is None) == output_is_none


@pytest.mark.parametrize("force_field_path", [None, "openff-1.0.0.offxml"])
def test_to_input_schema(force_field_path):

    input_schema = _to_input_schema(
        rich.get_console(),
        Molecule.from_smiles("CC"),
        force_field_path=force_field_path,
        target_torsion_smirks=tuple(),
        workflow_name="debug",
        workflow_file_name=None,
    )

    assert isinstance(input_schema, BespokeOptimizationSchema)
    assert input_schema.id == "bespoke_task_0"

    assert (
        "2021-08-16" if force_field_path is None else "2019-10-10"
    ) in input_schema.initial_force_field


def test_to_input_schema_file_not_found(tmpdir):

    console = rich.get_console()

    with console.capture() as capture:
        with pytest.raises(click.exceptions.Exit):
            _to_input_schema(
                console,
                Molecule.from_smiles("CC"),
                force_field_path="openff-1.2.1.offxml",
                target_torsion_smirks=tuple(),
                workflow_name="fake-workflow-name-123",
                workflow_file_name=None,
            )

    assert (
        "The specified workflow could not be found: fake-workflow-name-123"
        in capture.get()
    )


def test_to_input_schema_invalid_schema(tmpdir):

    console = rich.get_console()

    invalid_workflow_path = os.path.join(tmpdir, "some-invalid-schema.json")

    with open(invalid_workflow_path, "w") as file:
        json.dump({"invalid-filed": 1}, file)

    with console.capture() as capture:
        with pytest.raises(click.exceptions.Exit):

            _to_input_schema(
                console,
                Molecule.from_smiles("CC"),
                force_field_path="openff-1.2.1.offxml",
                target_torsion_smirks=tuple(),
                workflow_name=None,
                workflow_file_name=invalid_workflow_path,
            )

    assert "The workflow could not be parsed" in capture.get()


def test_submit_multi_molecule(tmpdir):

    console = rich.get_console()

    input_file_path = os.path.join(tmpdir, "mol.pdb")

    molecules = [Molecule.from_smiles(smiles) for smiles in ("ClCl", "BrBr")]
    Topology.from_molecules(molecules).to_file(
        input_file_path, positions=numpy.zeros((4, 3)) * unit.angstrom
    )

    with console.capture() as capture:
        with pytest.raises(click.exceptions.Exit):
            _submit(
                console,
                input_file_path=input_file_path,
                molecule_smiles=None,
                force_field_path="openff-2.0.0.offxml",
                target_torsion_smirks=tuple(),
                workflow_name="debug",
                workflow_file_name=None,
            )

    assert "only one molecule can currently" in capture.get()


def test_submit_invalid_schema(tmpdir):
    """Make sure to schema failures are cleanly handled."""

    input_file_path = os.path.join(tmpdir, "mol.sdf")
    Molecule.from_smiles("C").to_file(input_file_path, "SDF")

    with pytest.raises(click.exceptions.Exit):
        _submit(
            rich.get_console(),
            input_file_path=input_file_path,
            molecule_smiles=None,
            force_field_path="openff-2.0.0.offxml",
            target_torsion_smirks=tuple(),
            workflow_name=None,
            workflow_file_name=None,
        )


@pytest.mark.parametrize(
    "file, smiles",
    [
        pytest.param(
            get_data_file_path(
                os.path.join("test", "molecules", "ethane.sdf"),
                package_name="openff.bespokefit",
            ),
            None,
            id="file path",
        ),
        pytest.param(None, "CC", id="smiles"),
    ],
)
def test_submit(tmpdir, file, smiles):
    """Make sure to schema failures are cleanly handled."""

    settings = current_settings()

    with requests_mock.Mocker() as m:

        mock_href = (
            f"http://127.0.0.1:"
            f"{settings.BEFLOW_GATEWAY_PORT}"
            f"{settings.BEFLOW_API_V1_STR}/"
            f"{settings.BEFLOW_COORDINATOR_PREFIX}"
        )
        m.post(mock_href, text=CoordinatorPOSTResponse(self="", id="1").json())

        response_id = _submit(
            rich.get_console(),
            input_file_path=file,
            molecule_smiles=smiles,
            force_field_path="openff-2.0.0.offxml",
            target_torsion_smirks=tuple(),
            workflow_name="debug",
            workflow_file_name=None,
        )
        assert response_id == "1"


def test_submit_cli(runner, tmpdir):
    """Make sure to schema failures are cleanly handled."""

    settings = current_settings()

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
            submit_cli, args=["--file", input_file_path, "--workflow", "debug"]
        )

    assert output.exit_code == 0
    assert "workflow submitted: id=1" in output.output


@pytest.mark.parametrize(
    "file, smiles",
    [
        pytest.param("test.sdf", "CC", id="both defined."),
        pytest.param(None, None, id="Both missing"),
    ],
)
def test_submit_cli_mutual_exclusive_args(file, smiles):
    """
    Make sure an error is raised if we pass mutual exclusive args.
    """

    console = rich.get_console()

    with console.capture() as capture:
        with pytest.raises(click.exceptions.Exit):

            _submit_cli(
                input_file_path=file,
                molecule_smiles=smiles,
                workflow_name="default",
                workflow_file_name=None,
                target_torsion_smirks=tuple(),
                force_field_path=None,
            )

    assert (
        "[ERROR] The `file` and `smiles` arguments are mutually exclusive."
        in capture.get()
    )
