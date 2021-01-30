"""
Test for the bespoke-fit workflow generator.
"""

import pytest
from openforcefield.topology import Molecule

from openff.bespokefit.exceptions import ForceFieldError, OptimizerError
from openff.bespokefit.optimizers import (
    ForceBalanceOptimizer,
    deregister_optimizer,
    register_optimizer,
)
from openff.bespokefit.targets import AbInitio_SMIRNOFF
from openff.bespokefit.utils import get_data
from openff.bespokefit.workflow import WorkflowFactory
from openff.qcsubmit.testing import temp_directory


@pytest.mark.parametrize("forcefield", [
    pytest.param(("openff-1.0.0.offxml", None), id="Parsley 1.0.0"),
    pytest.param(("bespoke.offxml", ForceFieldError), id="Local forcefield"),
    pytest.param(("smirnoff99Frosst-1.0.7.offxml", None), id="Smirnoff99Frosst installed")
])
def test_workflow_forcefield_setter(forcefield):
    """
    Make sure we only accept forcefields that have been installed.
    """
    force_file, error = forcefield
    factory = WorkflowFactory()
    if error is None:
        factory.initial_forcefield = force_file
    else:
        with pytest.raises(ForceFieldError):
            factory.initial_forcefield = force_file


@pytest.mark.parametrize("optimization_data", [
    pytest.param(("ForceBalanceOptimizer", None), id="Forcebalance string pass"),
    pytest.param(("BadOptimizer", OptimizerError), id="Missing optimizer"),
    pytest.param((ForceBalanceOptimizer(optimization_targets=[AbInitio_SMIRNOFF()]), None), id="Forcebalance class with target.")
])
def test_adding_optimization_stages(optimization_data):
    """
    Test adding optimization stages to the workflow.
    """
    stage, error = optimization_data
    workflow = WorkflowFactory()

    if error is None:
        workflow.set_optimizer(optimizer=stage)
        assert workflow.optimizer is not None
    else:
        with pytest.raises(error):
            workflow.set_optimizer(optimizer=stage)


def test_adding_optimization_stages_missing():
    """
    Test adding an optimization stage with an optimizer which is not registered.
    """
    # first we need to remove the forcebalance optimizer
    fb = ForceBalanceOptimizer()
    deregister_optimizer(optimizer=fb)

    # now try and add it to the workflow
    workflow = WorkflowFactory()

    with pytest.raises(OptimizerError):
        workflow.set_optimizer(fb)

    # register it again
    register_optimizer(optimizer=fb)


def test_remove_optimization_stages():
    """
    Test removing optimization stages from the workflow.
    """

    workflow = WorkflowFactory(optimization_workflow=[ForceBalanceOptimizer()])
    workflow.clear_optimizer()
    assert workflow.optimizer is None


def test_workflow_export_import():
    """
    Test exporting and importing a workflow.
    """

    workflow = WorkflowFactory()
    # add fb and a target with non standard settings
    fb = ForceBalanceOptimizer(penalty_type="L1", optimization_targets=[AbInitio_SMIRNOFF(fragmentation=False)])
    workflow.set_optimizer(optimizer=fb)

    with temp_directory():
        workflow.export_workflow(file_name="test.yaml")
        # now read it back in
        workflow2 = WorkflowFactory.parse_file("test.yaml")
        assert workflow.dict() == workflow2.dict()


@pytest.mark.parametrize("optimizer_data",[
    pytest.param(([], OptimizerError), id="No Optimizer error"),
    pytest.param(([ForceBalanceOptimizer()], OptimizerError), id="Forcebalane no targets"),
    pytest.param(([ForceBalanceOptimizer(optimization_targets=[AbInitio_SMIRNOFF(fragmentation=False)])], None), id="Correct setup")
])
def test_make_fitting_schema(optimizer_data):
    """
    Test making a fitting schema for a simple molecule.
    """
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    workflow = WorkflowFactory()

    optimizers, error = optimizer_data
    for opt in optimizers:
        workflow.set_optimizer(optimizer=opt)

    if error is None:
        schema = workflow.create_fitting_schema(molecules=[ethane, ])
        assert schema.client == workflow.client
        assert schema.singlepoint_dataset_name == workflow.singlepoint_dataset_name
        assert schema.optimization_dataset_name == workflow.optimization_dataset_name
        assert schema.torsiondrive_dataset_name == workflow.torsiondrive_dataset_name
        # now we need to make sure the optimizer data is correct
        assert schema.optimizer_settings[optimizers[0].optimizer_name.lower()] == optimizers[0].dict(exclude={"optimization_targets"})
        assert schema.n_molecules == 1
        assert schema.n_tasks == 1
        # we need to make sure there is one TD target
        molecule_schema = schema.tasks[0]
        assert molecule_schema.molecule == ethane.to_smiles(isomeric=True, explicit_hydrogens=True, mapped=True)
        assert molecule_schema.off_molecule == ethane
        assert molecule_schema.n_tasks == 1
        assert molecule_schema.n_targets == 1
        assert molecule_schema.initial_forcefield == workflow.initial_forcefield
        task_schema = molecule_schema.workflow
        assert task_schema.optimizer_name == optimizers[0].optimizer_name

    else:
        with pytest.raises(error):
            _ = workflow.create_fitting_schema(molecules=[ethane, ])
