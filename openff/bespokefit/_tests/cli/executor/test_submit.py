import csv
import json
import os.path

import click.exceptions
import pytest
import requests
import requests_mock
import rich
from openff.toolkit.topology import Molecule
from openff.utilities import get_data_file_path

from openff.bespokefit._tests import does_not_raise
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

    # the shipped default.json is generated with this block of code
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
                force_field_path="openff-2.2.0.offxml",
                target_torsion_smirks=tuple(),
                default_qc_spec=None,
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
        default_qc_spec=None,
        workflow_name="debug",
        workflow_file_name=None,
    )

    assert isinstance(input_schema, BespokeOptimizationSchema)
    assert input_schema.id == "bespoke_task_0"

    # Default to Sage 2.2 if no force field is provided,
    # but 2019 if Parsley is provided
    assert (
        "2024-04-18" if force_field_path is None else "2019-10-10"
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
                default_qc_spec=None,
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
                default_qc_spec=None,
                workflow_name=None,
                workflow_file_name=invalid_workflow_path,
            )

    assert "The workflow could not be parsed" in capture.get()


def test_to_input_schema_overwrite_spec(tmpdir):
    """Make sure the CLI spec overwrites the workflow spec"""

    console = rich.get_console()

    input_schema = _to_input_schema(
        console=console,
        molecule=Molecule.from_smiles("CC"),
        force_field_path=None,
        target_torsion_smirks=tuple(),
        default_qc_spec=("xtb", "gfn2xtb", "none"),
        workflow_name="debug",  # this workflow has a rdkit spec by default
        workflow_file_name=None,
    )

    qc_spec = input_schema.stages[0].targets[0].calculation_specification
    assert qc_spec.program == "xtb"
    assert qc_spec.model.method == "gfn2xtb"
    assert qc_spec.model.basis is None


def test_to_input_schema_error_spec(tmpdir):
    """Make sure specification validation errors are raised."""

    console = rich.get_console()

    with console.capture() as capture:
        with pytest.raises(click.exceptions.Exit):
            _to_input_schema(
                console=console,
                molecule=Molecule.from_smiles("CC"),
                force_field_path=None,
                target_torsion_smirks=tuple(),
                default_qc_spec=("xtb", "gfn2xtb", "fake_basis"),
                workflow_name="debug",
                workflow_file_name=None,
            )

    assert "The QCSpecification is not valid." in capture.get()


def test_submit_multi_molecule(tmpdir):
    console = rich.get_console()

    with console.capture() as capture:
        with pytest.raises(click.exceptions.Exit):
            _submit(
                console,
                input_file_path=[],
                molecule_smiles=["[Cu+2].[O-]S(=O)(=O)[O-]"],
                force_field_path="openff-2.2.0.offxml",
                target_torsion_smirks=tuple(),
                default_qc_spec=None,
                workflow_name="debug",
                workflow_file_name=None,
                save_submission=False,
                allow_multiple_molecules=False,
            )

    assert "complexes are not supported" in capture.get()


def test_submit_invalid_schema(tmpdir):
    """Make sure to schema failures are cleanly handled."""

    input_file_path = os.path.join(tmpdir, "mol.sdf")
    Molecule.from_smiles("C").to_file(input_file_path, "SDF")

    with pytest.raises(click.exceptions.Exit):
        _submit(
            rich.get_console(),
            input_file_path=[
                input_file_path,
            ],
            molecule_smiles=[],
            force_field_path="openff-2.2.0.offxml",
            target_torsion_smirks=tuple(),
            default_qc_spec=None,
            workflow_name=None,
            workflow_file_name=None,
            save_submission=False,
            allow_multiple_molecules=False,
        )


@pytest.mark.parametrize(
    "file, smiles",
    [
        pytest.param(
            [
                get_data_file_path(
                    os.path.join("test", "molecules", "ethane.sdf"),
                    package_name="openff.bespokefit",
                )
            ],
            [],
            id="file path",
        ),
        pytest.param([], ["CC"], id="smiles"),
    ],
)
def test_submit(tmpdir, file, smiles):
    """Make sure to schema failures are cleanly handled."""

    with tmpdir.as_cwd():
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
                force_field_path="openff-2.2.0.offxml",
                target_torsion_smirks=tuple(),
                default_qc_spec=None,
                workflow_name="debug",
                workflow_file_name=None,
                save_submission=True,
                allow_multiple_molecules=False,
            )
            assert response_id == [
                "1",
            ]
            # check the submission file
            with open("submission.csv") as csv_file:
                submissions = csv.DictReader(csv_file)
                for row in submissions:
                    assert row["ID"] == "1"
                    assert row["SMILES"] == "CC"
                    if file:
                        assert row["FILE"] == file[0]


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
    assert "the following workflows were submitted" in output.output


def test_submit_file_and_smiles_cli(runner, tmpdir):
    """Make sure we can accept files and smiles combinations."""

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
            submit_cli,
            args=[
                "--file",
                input_file_path,
                "--workflow",
                "debug",
                "--smiles",
                "CCO",
                "--smiles",
                "CCN",
            ],
        )

    assert output.exit_code == 0
    assert "the following workflows were submitted" in output.output
    assert (
        "[✓] 3 molecules found" in output.output
    )  # make sure all input molecules are included in the submission


def test_submit_cli_errors(tmpdir):
    """Make sure errors are caught by submit_cli"""

    console = rich.get_console()

    settings = current_settings()

    with requests_mock.Mocker() as m:
        mock_href = (
            f"http://127.0.0.1:"
            f"{settings.BEFLOW_GATEWAY_PORT}"
            f"{settings.BEFLOW_API_V1_STR}/"
            f"{settings.BEFLOW_COORDINATOR_PREFIX}"
        )
        m.register_uri(method="post", url=mock_href, exc=requests.ConnectionError)
        with console.capture() as capture:
            with pytest.raises(click.exceptions.Exit):
                _submit_cli(
                    input_file_path=None,
                    molecule_smiles=["CC"],
                    workflow_name="default",
                    workflow_file_name=None,
                    target_torsion_smirks=tuple(),
                    default_qc_spec=None,
                    force_field_path=None,
                    save_submission=False,
                )

        assert "[ERROR] failed to connect to the bespoke executor" in capture.get()
