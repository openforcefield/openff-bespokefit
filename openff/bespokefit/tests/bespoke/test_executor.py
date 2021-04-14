"""
Tests for the executor class which runs and error cycles and optimizations.
The test are set out in
"""
import os

import pytest
from openff.qcsubmit.results import TorsionDriveCollectionResult
from qcportal import FractalClient

from openff.bespokefit.bespoke import Executor
from openff.bespokefit.utilities import get_data_file_path, temporary_cd


@pytest.mark.xfail(
    reason="failure expected until FB targets support BespokeQCData sets"
)
def test_optimizer_explicit(bespoke_optimization_schema):
    """
    Run the optimizer process in the main thread to make sure it works.
    """
    # now make the schema
    schema = bespoke_optimization_schema

    result = TorsionDriveCollectionResult.parse_file(
        get_data_file_path(
            os.path.join("test", "qc-datasets", "biphenyl", "biphenyl.json.xz"),
        )
    )
    schema.update_with_results(results=result)

    # now submit to the executor
    execute = Executor()
    # we dont need the server here
    # put a task in the opt queue then kill it
    execute.total_tasks = 1
    execute.opt_queue.put(schema)

    with temporary_cd():

        execute.optimizer()

        # find the task in the finished queue
        result_schema = execute.finished_tasks.get()
        smirks = result_schema.tasks[0].final_smirks

        # make sure they have been updated
        for smirk in smirks:
            for term in smirk.terms.values():
                assert float(term.k.split()[0]) != 1e-5


# def test_full_run_xtb(fractal_compute_server):
#     """
#     Test a full run through using xtb, this will generate and run the tasks on the snowflake and then run the fitting.
#     """
#     if not has_program("xtb"):
#         pytest.skip("Xtb not installed")
#
#     # first build the workflow with biphenyl
#     biphenyl = Molecule.from_file(get_data("biphenyl.sdf"))
#     workflow = WorkflowFactory()
#     fb = ForceBalanceOptimizer()
#     target = AbInitio_SMIRNOFF()
#     spec = QCSpec(method="gfn2xtb", basis=None, program="xtb", spec_name="default")
#     target.qc_spec = spec
#     # set the spec to use xtb
#     fb.set_optimization_target(target=target)
#     workflow.set_optimizer(fb)
#     schema = workflow.fitting_schema_from_molecules(molecules=biphenyl, processors=1)
#     execute = Executor()
#     client = FractalClient(fractal_compute_server)
#     with temp_directory():
#         result = execute.execute(fitting_schema=schema, client=client)
#         # try and get the final parameters
#         task = result.tasks[0]
#         assert task.target_smirks != task.final_smirks
#         assert task.final_smirks is not None
#         _ = task.get_final_forcefield(generate_bespoke_terms=True)


def test_error_cycle_complete(bespoke_optimization_schema):
    """
    Try and error cycle a task which is complete in qcarchive this should cause the task
    result to be collected and put into the optimization queue.
    """

    client = FractalClient()

    execute = Executor()
    # fake the dataset name
    execute._dataset_name = "OpenFF-benchmark-ligand-fragments-v1.0"

    task = bespoke_optimization_schema
    tasks = list(task.get_task_map().keys())

    # fake the task map
    execute.task_map = {
        tasks[
            0
        ]: "[h]c1c([c:1]([c:2](c(c1[h])[h])[c:3]2[c:4](c(c(c(c2[h])cl)[h])[h])[h])[h])[h]"
    }
    execute._error_cycle_task(task=task, client=client)

    # the result should be collected and the task is now in the opt queue
    opt_task = execute.opt_queue.get(timeout=5)
    assert opt_task.ready_for_fitting is True


def test_collecting_results(bespoke_optimization_schema):
    """
    Make sure that tasks are collected correctly from a QCArchive instance.
    """

    client = FractalClient()

    # now submit to the executor
    executor = Executor()
    # change to make sure we search the correct dataset
    executor._dataset_name = "OpenFF-benchmark-ligand-fragments-v1.0"
    # fake a collection dict
    to_collect = {
        "torsion1d": {
            "default": [
                "[h]c1c([c:1]([c:2](c(c1[h])[h])[c:3]2[c:4](c(c(c(c2[h])cl)[h])[h])[h])[h])[h]",
            ]
        },
        "optimization": {},
        "hessian": {},
    }
    # now let the executor update the task
    executor.collect_task_results(
        optimization=bespoke_optimization_schema,
        collection_dict=to_collect,
        client=client,
    )
    # make sure it worked
    assert bespoke_optimization_schema.ready_for_fitting is True


def test_submit_new_tasks(fractal_compute_server, bespoke_optimization_schema):
    """Make sure that any new tasks which are generated/found are added to the archive
    instance.
    """

    client = FractalClient(fractal_compute_server)

    executor = Executor()
    # make sure new tasks are submitted
    response = executor.submit_new_tasks(
        optimization=bespoke_optimization_schema, client=client
    )

    assert response == {"OpenFF Bespoke-fit": {"default": 1}}


# def test_executor_no_collection(fractal_compute_server):
#     """
#     Test using the executor when there are no tasks to collect only optimizations to run.
#     """
#     client = FractalClient(fractal_compute_server)
#     biphenyl = Molecule.from_file(file_path=get_data("biphenyl.sdf"), file_format="sdf")
#     # now make the schema
#     schema = get_fitting_schema(molecules=biphenyl)
#     result = TorsionDriveCollectionResult.parse_file(get_data("biphenyl.json.xz"))
#     schema.update_with_results(results=result)
#
#     # now submit to the executor
#     execute = Executor()
#     # there are no collection tasks
#     assert execute.task_map == {}
#     # submit the optimization
#     with temp_directory():
#         result_schema = execute.execute(fitting_schema=schema, client=client)
#         # make sure we can generate the final forcefield
#         _ = result_schema.tasks[0].get_final_forcefield(generate_bespoke_terms=True, drop_out_value=5e-5)
#         # make sure they are all finished
#         assert execute.total_tasks == 0
#         # check the results have been saved
#         smirks = result_schema.tasks[0].final_smirks
#         # make sure they have been updated
#         for smirk in smirks:
#             for term in smirk.terms.values():
#                 assert float(term.k.split()[0]) != 1e-5
#
#         # now round load up the results
#         schema = FittingSchema.parse_file("final_results.json.xz")
#         # make sure all tasks are complete
#         assert schema.tasks[0].status == Status.Complete
