import os.path

import click.exceptions
import pytest
import rich
from openff.qcsubmit.results import TorsionDriveResultCollection
from openff.utilities import get_data_file_path

from openff.bespokefit._tests import does_not_raise
from openff.bespokefit.cli.cache import (
    _connect_to_qcfractal,
    _results_from_file,
    _update_from_qcsubmit_result,
    update_cli,
)


@pytest.mark.parametrize(
    "filename, expected_raises, output",
    [
        pytest.param(
            "torsion_collection.json",
            does_not_raise(),
            "torsion_collection.json loaded as a `TorsionDriveResultCollection`.",
            id="torsiondrive",
        ),
        pytest.param(
            "optimization_collection.json",
            does_not_raise(),
            "optimization_collection.json loaded as a `OptimizationResultCollection`",
            id="optimization",
        ),
        pytest.param(
            "hessian_collection.json",
            pytest.raises(click.exceptions.Exit),
            "[ERROR] The result file",
            id="hessian",
        ),
    ],
)
def test_results_from_file(filename, expected_raises, output):
    """
    Test loading qcsubmit results files.
    """

    console = rich.get_console()

    with console.capture() as capture:
        file_path = get_data_file_path(
            os.path.join("test", "schemas", filename), package_name="openff.bespokefit"
        )

        with expected_raises:
            _ = _results_from_file(console=console, input_file_path=file_path)

    assert output in capture.get().replace("\n", "")


@pytest.mark.parametrize(
    "address, expected_raises, expected_output",
    [
        pytest.param(
            "api.qcarchive.molssi.org:443",
            does_not_raise(),
            "[✓] connected to QCFractal",
            id="QCArchive",
        ),
        pytest.param(
            "api.qcarchive.molssi.com:1",
            pytest.raises(click.exceptions.Exit),
            "[ERROR] Unable to connect to QCFractal due to the following error.",
            id="Error",
        ),
    ],
)
def test_connecting_to_fractal_address(address, expected_raises, expected_output):
    """
    Test connecting to fractal from using an address.
    """
    console = rich.get_console()

    with console.capture() as capture:
        with expected_raises:
            _ = _connect_to_qcfractal(
                console=console, qcf_address=address, qcf_config=None
            )
    assert expected_output in capture.get().replace("\n", "")


def test_connecting_to_fractal_file():
    """
    Try to connect to the QCArchive using an config file.
    """

    console = rich.get_console()

    with console.capture() as capture:
        _ = _connect_to_qcfractal(
            console=console,
            qcf_address="",
            qcf_config=get_data_file_path(
                os.path.join("test", "miscellaneous", "qcfractal.yaml"),
                package_name="openff.bespokefit",
            ),
        )
    assert "[✓] connected to QCFractal" in capture.get()


def test_update_from_qcsubmit(redis_connection):
    """
    Test adding a mocked result to a local redis instance.
    """

    console = rich.get_console()
    qcsubmit_result = TorsionDriveResultCollection.parse_file(
        get_data_file_path(
            os.path.join("test", "schemas", "torsion_collection.json"),
            package_name="openff.bespokefit",
        )
    )

    with console.capture() as capture:
        _update_from_qcsubmit_result(
            console=console,
            qcsubmit_results=qcsubmit_result,
            redis_connection=redis_connection,
        )
    assert "[✓] local results built" in capture.get()
    assert "1/1 results cached" in capture.get()

    # find the result in redis
    task_id = redis_connection.hget(
        name="qcgenerator:task-ids",
        key="3e44753b523c792590fbfbec096b238630d170165772021360b01e47712c49f2d5639cdb947dea31efa35a640bebd5d233871553a8c56d1a316b91305d699a04",
    )
    if task_id is None:
        # try and find the rdkit based hash
        task_id = redis_connection.hget(
            name="qcgenerator:task-ids",
            key="fa67a801ef9bada2f0f2b76f13b761e2f53d640c883cc50d900c0639de25e929db207c6ff8680e19eee0d6c8c28986a67533e7d6e16bd8f8d26f32922b12c08b",
        )
    assert redis_connection.hget("qcgenerator:types", task_id) == b"torsion1d"


def test_cache_cli_fractal(runner, tmpdir):
    """Test running the cache update cli."""

    output = runner.invoke(
        update_cli,
        args=[
            "--qcf-dataset",
            "OpenFF Gen 2 Torsion Set 6 supplemental 2",
            "--qcf-datatype",
            "torsion",
        ],
    )
    assert output.exit_code == 0, print(output.output)
    assert "4. saving local cache" in output.output
