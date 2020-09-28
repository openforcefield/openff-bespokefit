"""
Forcebalance specific optimizer testing.
"""

import os
import shutil

import pytest
from openforcefield.topology import Molecule

from qcsubmit.testing import temp_directory

from ...common_structures import Status
from ...exceptions import TargetNotSetError
from ...optimizers import ForceBalanceOptimizer
from ...schema.fitting import WorkflowSchema
from ...targets import AbInitio_SMIRNOFF, TorsionProfile_SMIRNOFF
from ...utils import get_data


def ethane_workflow(target) -> WorkflowSchema:
    """
    Create a workflow schema which targets the rotatable bond in ethane.
    """
    mol = Molecule.from_smiles("CC")
    target = target()
    workflow = WorkflowSchema(optimizer_name="forcebalanceoptimizer", job_id=mol.to_smiles(), targets=[target.generate_fitting_schema(molecule=mol)])
    return workflow


def test_forcebalance_name_change():
    """
    Check that the optimizer name can not be changed.
    """
    fb = ForceBalanceOptimizer()
    # try a random name
    fb.optimizer_name = "fancy_opt"
    assert fb.optimizer_name.lower() != "fancy_opt"
    # try and just lower case
    fb.optimizer_name = "forcebalanceoptimizer"
    assert fb.optimizer_name.lower() == "forcebalanceoptimizer"


def test_forcebalance_provenance():
    """
    Make sure the correct forcebalance version is returned.
    """
    import forcebalance
    fb = ForceBalanceOptimizer()
    provenance = fb.provenance()
    assert provenance["forcebalance"] == forcebalance.__version__


def test_forcebalance_available():
    """
    Make sure forcebalance is correctly found when installed.
    """

    assert ForceBalanceOptimizer.is_available() is True


def test_generate_opt_in():
    """
    Test generating the optimize in file with various input settings.
    """
    fb = ForceBalanceOptimizer(penalty_type="L1", max_iterations=150)

    # make sure an error is raised if the targets were not set
    with temp_directory():
        with pytest.raises(TargetNotSetError):
            fb.generate_optimize_in(priors={"test": 1.23}, fitting_targets={"AbInitio_SMIRNOFF": ["job1", "job2"]})

        # now set them and run again
        fb.set_optimization_target(AbInitio_SMIRNOFF())
        fb.generate_optimize_in(priors={"test": 1.23}, fitting_targets={"AbInitio_SMIRNOFF": ["job1", "job2"]})

        # now load in the file and check the attributes
        with open("optimize.in") as opt_in:
            data = opt_in.readlines()
            assert "   test :  1.23\n" in data
            assert "penalty_type L1\n" in data
            assert "maxstep 150\n" in data
            assert "type AbInitio_SMIRNOFF\n" in data
            assert "name job1\n" in data
            assert "name job2\n" in data


@pytest.mark.parametrize("output", [
    pytest.param(("complete.out", Status.Complete), id="Complete"),
    pytest.param(("error.out", Status.Error), id="Error"),
    pytest.param(("running.out", Status.Optimizing), id="Running")
])
def test_forcebalance_readoutput(output):
    """
    Test reading the output of a forcebalance run.
    """
    file_name, status = output
    with temp_directory():
        # copy the file over
        shutil.copy(get_data(file_name), "optimize.out")
        # now we have to make sum dummy folders
        results_folder = os.path.join("result", "optimize")
        os.makedirs(results_folder, exist_ok=True)
        with open(os.path.join(results_folder, "bespoke_10.offxml"), "w") as xml:
            xml.write("test")
        fb = ForceBalanceOptimizer()
        result = fb.read_output()
        assert result["status"] == status
        assert "bespoke_10.offxml" in result["forcefield"]


def test_forcebalance_collect_result_error():
    """
    Test trying to collect the result when the workflow has an error.
    """
    workflow = ethane_workflow(target=AbInitio_SMIRNOFF)
    # we need to set up a dummy folder with the error
    with temp_directory():
        # copy the file over
        shutil.copy(get_data("error.out"), "optimize.out")
        results_folder = os.path.join("result", "optimize")
        os.makedirs(results_folder, exist_ok=True)
        with open(os.path.join(results_folder, "bespoke_10.offxml"), "w") as xml:
            xml.write("test")
        fb = ForceBalanceOptimizer()
        result_workflow = fb.collect_results(workflow=workflow)
        assert result_workflow.status == Status.Error


def test_forcebalance_collect_results():
    """
    Test trying to collect results that have been successful and updated the parameters.
    """
    workflow = ethane_workflow(target=AbInitio_SMIRNOFF)
    # first make sure the target smirks are set to the default value
    target_smirks = workflow.target_smirks
    for smirk in target_smirks:
        for param in smirk.terms.values():
            assert param.k == "1e-05 * mole**-1 * kilocalorie"

    # set up the dummy output folder
    with temp_directory():
        # copy the file over
        shutil.copy(get_data("complete.out"), "optimize.out")
        results_folder = os.path.join("result", "optimize")
        os.makedirs(results_folder, exist_ok=True)
        ff_path = os.path.join(results_folder, "bespoke_1.offxml")
        shutil.copy(get_data("bespoke_1.offxml"), ff_path)
        fb = ForceBalanceOptimizer()
        result_workflow = fb.collect_results(workflow=workflow)
        # make sure the smirks have been updated
        new_smirks = result_workflow.target_smirks
        for smirk in new_smirks:
            for param in smirk.terms.values():
                assert param.k != "1e-05 * mole**-1 * kilocalorie"


@pytest.mark.parametrize("optimization_target", [
    pytest.param(AbInitio_SMIRNOFF, id="AbInitio_SMIRNOFF"),
    pytest.param(TorsionProfile_SMIRNOFF, id="TorsionProfile_SMIRNOFF"),
])
def test_forcebalance_optimize(optimization_target):
    """
    Test running the ful optimization stage for ethane using different targets.
    The data has been precomputed using ani2x.
    """
    from qcsubmit.results import TorsionDriveCollectionResult
    workflow = ethane_workflow(target=optimization_target)
    with temp_directory():
        # load the computed results and add them to the workflow
        torsiondrive_result = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
        workflow.update_with_results(results=[torsiondrive_result, ])
        # setup the optimizer
        fb = ForceBalanceOptimizer()
        result = fb.optimize(workflow=workflow, initial_forcefield="openff_unconstrained-1.2.0.offxml")
        assert result.status == Status.Complete
        new_smirks = result.target_smirks
        for smirk in new_smirks:
            for param in smirk.terms.values():
                assert param.k != "1e-05 * mole**-1 * kilocalorie"
