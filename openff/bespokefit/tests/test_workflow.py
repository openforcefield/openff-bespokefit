"""
Test for the bespoke-fit workflow generator.
"""

import pytest
from openforcefield.topology import Molecule
from qcfractal.interface import FractalClient

from openff.bespokefit.exceptions import (
    ForceFieldError,
    FragmenterError,
    OptimizerError,
    TargetNotSetError,
)
from openff.bespokefit.optimizers import (
    ForceBalanceOptimizer,
    deregister_optimizer,
    register_optimizer,
)
from openff.bespokefit.targets import AbInitio_SMIRNOFF
from openff.bespokefit.utils import get_data
from openff.bespokefit.workflow import WorkflowFactory
from openff.qcsubmit.results import TorsionDriveCollectionResult
from openff.qcsubmit.testing import temp_directory

bace_entries = ['[h]c1c([c:1]([c:2](c(c1[h])[h])[c:3]2[c:4](c(c(c(c2[h])cl)[h])[h])[h])[h])[h]',
                "[h]c1c([c:1]([c:2](c(c1[h])[h])[c@:3]2(c(=o)n(c(=[n+:4]2[h])n([h])[h])c([h])([h])[h])c3(c(c3([h])[h])([h])[h])[h])[h])[h]",
                "[h]c1c(c(c(c(c1[h])[h])[c@:3]2(c(=o)n(c(=[n+:4]2[h])n([h])[h])c([h])([h])[h])[c:2]3([c:1](c3([h])[h])([h])[h])[h])[h])[h]"]

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
        workflow.export_workflow(file_name="test.json")
        # now read it back in
        workflow2 = WorkflowFactory.parse_file("test.json")
        assert workflow.dict() == workflow2.dict()


def test_pre_run_check_no_opt():
    """
    Make sure that the pre run check throws an error if there is no optimiser.
    """
    workflow = WorkflowFactory()
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")

    with pytest.raises(OptimizerError):
        _ = workflow.fitting_schema_from_molecules(molecules=ethane)


def test_pre_run_check_no_target():
    """
    Make sure that the pre run check catches if there are no targets set up
    """
    workflow = WorkflowFactory()
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    fb = ForceBalanceOptimizer()
    workflow.set_optimizer(optimizer=fb)
    with pytest.raises(OptimizerError):
        _ = workflow.fitting_schema_from_molecules(molecules=ethane)


def test_pre_run_check_no_frag():
    """
    Make sure the pre run check catches if there is no fragmentation method set.
    """
    workflow = WorkflowFactory()
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    fb = ForceBalanceOptimizer()
    fb.set_optimization_target(target=AbInitio_SMIRNOFF())
    workflow.set_optimizer(optimizer=fb)
    workflow.fragmentation_engine = None
    with pytest.raises(FragmenterError):
        _ = workflow.fitting_schema_from_molecules(molecules=ethane)


def test_pre_run_check_no_params():
    """
    Make sure that the pre run check catches if we have not set any parameters to optimise, like bond length.
    """
    workflow = WorkflowFactory()
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    fb = ForceBalanceOptimizer()
    fb.set_optimization_target(target=AbInitio_SMIRNOFF())
    workflow.set_optimizer(optimizer=fb)
    workflow.target_parameters = []
    with pytest.raises(TargetNotSetError):
        _ = workflow.fitting_schema_from_molecules(molecules=ethane)


def test_pre_run_check_no_smirks():
    """
    Make sure that the pre run check checks that some target smirks have been supplied.
    """
    workflow = WorkflowFactory()
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    fb = ForceBalanceOptimizer()
    fb.set_optimization_target(target=AbInitio_SMIRNOFF())
    workflow.set_optimizer(optimizer=fb)
    workflow.target_smirks = []
    with pytest.raises(TargetNotSetError):
        _ = workflow.fitting_schema_from_molecules(molecules=ethane)


def test_make_fitting_schema_from_molecules():
    """
    Test making a fitting schema for a simple molecule using the default settings.
    Bace is a small molecule that should split into 2 fragments for a total of 3 torsiondrives.
    """
    bace = Molecule.from_file(file_path=get_data("bace.sdf"), file_format="sdf")
    workflow = WorkflowFactory()
    fb = ForceBalanceOptimizer()
    fb.set_optimization_target(target=AbInitio_SMIRNOFF())
    workflow.set_optimizer(optimizer=fb)

    schema = workflow.fitting_schema_from_molecules(molecules=bace)
    # make sure one ethane torsion dirve is made
    assert schema.n_molecules == 1
    assert schema.n_tasks == 3
    assert bace in schema.molecules
    assert bace not in schema.entry_molecules
    # get the qcsubmit dataset
    datasets = schema.generate_qcsubmit_datasets()
    assert len(datasets) == 1
    assert datasets[0].dataset_type == "TorsiondriveDataset"
    assert datasets[0].n_records == 3


def test_task_from_molecule():
    """
    Test the workflow function which makes the optimization schema from a molecule
    """
    bace = Molecule.from_file(file_path=get_data("bace.sdf"), file_format="sdf")
    workflow = WorkflowFactory()
    fb = ForceBalanceOptimizer()
    fb.set_optimization_target(target=AbInitio_SMIRNOFF())
    workflow.set_optimizer(optimizer=fb)

    opt_schema = workflow._task_from_molecule(molecule=bace, index=1)
    assert opt_schema.initial_forcefield == workflow.initial_forcefield
    assert opt_schema.optimizer_name == fb.optimizer_name
    assert opt_schema.job_id == "bespoke_task_1"
    assert bool(opt_schema.target_smirks) is True
    assert opt_schema.target_parameters == workflow.target_parameters
    assert opt_schema.target_molecule.molecule == bace
    assert opt_schema.n_tasks == 3
    assert opt_schema.n_targets == 1


@pytest.mark.parametrize("combine", [
    pytest.param(True, id="combine"),
    pytest.param(False, id="no combine")
])
def test_sort_results(combine):
    """
    Test sorting the results before making a fitting schema with and without combination.
    """
    # load up the fractal client
    client = FractalClient()
    # grab a dataset with bace fragments in it
    result = TorsionDriveCollectionResult.from_server(client=client, spec_name="default", dataset_name="OpenFF-benchmark-ligand-fragments-v1.0", final_molecule_only=True, subset=bace_entries)
    workflow = WorkflowFactory()
    # now sort the results
    all_results = workflow._sort_results(results=result, combine=combine)
    if combine:
        assert len(all_results) == 2
    else:
        assert len(all_results) == 3


def test_task_from_results():
    """
    Test making an individual task from a set of results
    """
    # load a client and pull some results
    client = FractalClient()
    # grab a dataset with small fragments in it
    result = TorsionDriveCollectionResult.from_server(client=client, spec_name="default",
                                                      dataset_name="OpenFF-benchmark-ligand-fragments-v1.0",
                                                      final_molecule_only=True, subset=bace_entries[:1])
    # grab the only result
    result = list(result.collection.values())[0]
    # set up the workflow
    workflow = WorkflowFactory()
    fb = ForceBalanceOptimizer()
    fb.set_optimization_target(target=AbInitio_SMIRNOFF())
    workflow.set_optimizer(optimizer=fb)
    # this should be a simple biphenyl molecule
    opt_schema = workflow._task_from_results(results=[result, ], index=1)

    assert opt_schema.initial_forcefield == workflow.initial_forcefield
    assert opt_schema.optimizer_name == fb.optimizer_name
    assert opt_schema.job_id == "bespoke_task_1"
    assert bool(opt_schema.target_smirks) is True
    assert opt_schema.target_parameters == workflow.target_parameters
    assert result.molecule == opt_schema.target_molecule.molecule
    assert opt_schema.n_tasks == 1
    assert opt_schema.n_targets == 1
    assert opt_schema.ready_for_fitting is True


def test_make_fitting_schema_from_results():
    """
    Test that new fitting schemas can be made from results and that all results are full
    """
    # build the workflow
    workflow = WorkflowFactory()
    fb = ForceBalanceOptimizer()
    fb.set_optimization_target(target=AbInitio_SMIRNOFF())
    workflow.set_optimizer(optimizer=fb)

    # set up the client and load the results
    # load a client and pull some results
    client = FractalClient()
    # grab a dataset with small fragments in it
    result = TorsionDriveCollectionResult.from_server(client=client, spec_name="default",
                                                      dataset_name="OpenFF-benchmark-ligand-fragments-v1.0",
                                                      final_molecule_only=True, subset=bace_entries)
    schema = workflow.fitting_schema_from_results(results=result, combine=True)
    # there should be 2 total molecules as we have combined two results
    assert schema.n_molecules == 2
    # there are a total of 3 torsiondrives
    assert schema.n_tasks == 3
    # make sure each task has results and is ready to fit
    for task in schema.tasks:
        assert task.ready_for_fitting is True
