"""
Forcebalance specific optimizer testing.
"""

import os
import shutil
import subprocess

import numpy as np
import pytest
from openff.utilities import get_data_file_path, temporary_cd

from openff.bespokefit.optimizers import ForceBalanceOptimizer
from openff.bespokefit.schema.fitting import BaseOptimizationSchema
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.results import (
    BespokeOptimizationResults,
    OptimizationResults,
)


@pytest.fixture()
def forcebalance_results_directory(tmpdir):

    # copy the file over
    shutil.copy(
        get_data_file_path(
            os.path.join("test", "force-balance", "complete.out"), "openff.bespokefit"
        ),
        os.path.join(tmpdir, "optimize.out"),
    )

    # now we have to make some dummy folders
    results_folder = os.path.join(tmpdir, "result", "optimize")
    os.makedirs(results_folder, exist_ok=True)

    shutil.copy(
        get_data_file_path(
            os.path.join("test", "force-fields", "bespoke.offxml"), "openff.bespokefit"
        ),
        os.path.join(results_folder, "force-field.offxml"),
    )

    return tmpdir


def test_forcebalance_name():
    assert ForceBalanceOptimizer.name() == "ForceBalance"


def test_forcebalance_description():
    expected_message = "A systematic force field optimization tool"
    assert expected_message in ForceBalanceOptimizer.description()


def test_forcebalance_provenance():
    """
    Make sure the correct forcebalance version is returned.
    """
    import forcebalance
    import openff.toolkit

    provenance = ForceBalanceOptimizer.provenance()

    assert provenance["forcebalance"] == forcebalance.__version__
    assert provenance["openff.toolkit"] == openff.toolkit.__version__


def test_forcebalance_available():
    """
    Make sure forcebalance is correctly found when installed.
    """

    assert ForceBalanceOptimizer.is_available() is True


def test_forcebalance_schema_class():
    assert ForceBalanceOptimizer._schema_class() == ForceBalanceSchema


@pytest.mark.parametrize(
    "output",
    [
        pytest.param(("complete.out", "success", None), id="Complete run"),
        pytest.param(
            ("error.out", "errored", "ConvergenceFailure"), id="Convergence error"
        ),
        pytest.param(("running.out", "running", None), id="Running "),
    ],
)
def test_forcebalance_read_output(output):
    """Test reading the output of a forcebalance run."""

    file_name, status, error_type = output

    with temporary_cd():

        # copy the output file over
        shutil.copy(
            get_data_file_path(
                os.path.join("test", "force-balance", file_name), "openff.bespokefit"
            ),
            "optimize.out",
        )

        # now we have to make some dummy folders
        results_folder = os.path.join("result", "optimize")
        os.makedirs(results_folder, exist_ok=True)

        with open(os.path.join(results_folder, "force-field.offxml"), "w") as xml:
            xml.write("test")

        result = ForceBalanceOptimizer._read_output("")

        assert result["status"] == status

        if error_type is None:
            assert result["error"] is None
        else:
            assert result["error"].type == error_type

        assert "force-field.offxml" in result["forcefield"]


@pytest.mark.parametrize(
    "input_schema_fixture, expected_type",
    [
        ("bespoke_optimization_schema", BespokeOptimizationResults),
        ("general_optimization_schema", OptimizationResults),
    ],
)
def test_forcebalance_collect_general_results(
    input_schema_fixture, expected_type, forcebalance_results_directory, request
):
    """Test trying to collect results that have been successful and updated the
    parameters.
    """

    input_schema: BaseOptimizationSchema = request.getfixturevalue(input_schema_fixture)

    results = ForceBalanceOptimizer._collect_results(
        forcebalance_results_directory, schema=input_schema
    )

    assert isinstance(results, expected_type)

    initial_values = input_schema.initial_parameter_values
    refit_values = results.refit_parameter_values

    for parameter_smirks in initial_values:
        initial_parameters = initial_values[parameter_smirks]
        refit_parameters = refit_values[parameter_smirks]

        for attribute in initial_parameters:
            initial_parameter = initial_parameters[attribute]
            refit_parameter = refit_parameters[attribute]

            refit_value = refit_parameter.value_in_unit(initial_parameter.unit)
            initial_value = initial_parameter.value_in_unit(initial_parameter.unit)

            assert not np.isclose(initial_value, refit_value)


def test_forcebalance_optimize(
    forcebalance_results_directory, general_optimization_schema, monkeypatch
):

    # Patch the call to ForceBalance so that it doesn't need to run.
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: None)

    with temporary_cd(str(forcebalance_results_directory)):
        results = ForceBalanceOptimizer._optimize(general_optimization_schema)

    assert results.status == "success"
