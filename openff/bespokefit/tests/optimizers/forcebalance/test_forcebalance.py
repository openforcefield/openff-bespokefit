"""
Forcebalance specific optimizer testing.
"""

import os
import shutil
import subprocess

import pytest

from openff.bespokefit.optimizers import ForceBalanceOptimizer
from openff.bespokefit.schema.fitting import Status
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.results import (
    BespokeOptimizationResults,
    OptimizationResults,
)
from openff.bespokefit.utilities import get_data_file_path, temporary_cd


@pytest.fixture()
def forcebalance_results_directory(tmpdir):

    # copy the file over
    shutil.copy(
        get_data_file_path(os.path.join("test", "force-balance", "complete.out")),
        os.path.join(tmpdir, "optimize.out"),
    )

    # now we have to make some dummy folders
    results_folder = os.path.join(tmpdir, "result", "optimize")
    os.makedirs(results_folder, exist_ok=True)

    shutil.copy(
        get_data_file_path(os.path.join("test", "force-fields", "bespoke.offxml")),
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
        pytest.param(("complete.out", Status.Complete), id="Complete run"),
        pytest.param(("error.out", Status.ConvergenceError), id="Convergence error"),
        pytest.param(("running.out", Status.Optimizing), id="Running "),
    ],
)
def test_forcebalance_read_output(output):
    """
    Test reading the output of a forcebalance run.
    """
    file_name, status = output

    with temporary_cd():

        # copy the file over
        shutil.copy(
            get_data_file_path(os.path.join("test", "force-balance", file_name)),
            "optimize.out",
        )

        # now we have to make some dummy folders
        results_folder = os.path.join("result", "optimize")
        os.makedirs(results_folder, exist_ok=True)

        with open(os.path.join(results_folder, "force-field.offxml"), "w") as xml:
            xml.write("test")

        result = ForceBalanceOptimizer._read_output("")

        assert result["status"] == status
        assert "force-field.offxml" in result["forcefield"]


def test_forcebalance_collect_general_results(
    forcebalance_results_directory, general_optimization_schema
):
    """
    Test trying to collect results that have been successful and updated the parameters.
    """

    results = ForceBalanceOptimizer._collect_results(
        forcebalance_results_directory, schema=general_optimization_schema
    )

    assert isinstance(results, OptimizationResults)


def test_forcebalance_collect_bespoke_results(
    forcebalance_results_directory, bespoke_optimization_schema
):
    """
    Test trying to collect results that have been successful and updated the parameters.
    """

    # first make sure the target smirks are set to the default value
    target_smirks = bespoke_optimization_schema.target_smirks

    for smirk in target_smirks:
        for param in smirk.terms.values():
            # starting value
            assert param.k == "1.048715180139 * mole**-1 * kilocalorie"

    results = ForceBalanceOptimizer._collect_results(
        forcebalance_results_directory, schema=bespoke_optimization_schema
    )

    assert isinstance(results, BespokeOptimizationResults)

    # make sure the smirks have been updated
    new_smirks = results.final_smirks

    for smirk in new_smirks:
        for param in smirk.terms.values():
            assert param.k != "1.048715180139 * mole**-1 * kilocalorie"


def test_forcebalance_optimize(
    forcebalance_results_directory, general_optimization_schema, monkeypatch
):

    # Patch the call to ForceBalance so that it doesn't need to run.
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: None)

    with temporary_cd(str(forcebalance_results_directory)):
        results = ForceBalanceOptimizer._optimize(general_optimization_schema)

    assert results.status == Status.Complete


# @pytest.mark.parametrize("optimization_target", [
#     pytest.param(AbInitio_SMIRNOFF, id="AbInitio_SMIRNOFF"),
#     pytest.param(TorsionProfile_SMIRNOFF, id="TorsionProfile_SMIRNOFF"),
# ])
# def test_forcebalance_optimize(optimization_target):
#     """
#     Test running the full optimization stage for a simple biphenyl system using
#     different targets.
#     The data has been extracted from qcarchive.
#     """
#     from openff.qcsubmit.results import TorsionDriveCollectionResult
#     workflow = biphenyl_workflow(target=optimization_target)
#     with temp_directory():
#         # load the computed results and add them to the workflow
#         torsiondrive_result = TorsionDriveCollectionResult.parse_file(
#             get_data("biphenyl.json.xz")
#         )
#         workflow.update_with_results(results=torsiondrive_result)
#         # setup the optimizer
#         fb = ForceBalanceOptimizer()
#         result = fb.optimize(schema=workflow)
#         assert result.status == Status.Complete
#         new_smirks = result.target_smirks
#         for smirk in new_smirks:
#             for param in smirk.terms.values():
#                 assert param.k != "1e-05 * mole**-1 * kilocalorie"
