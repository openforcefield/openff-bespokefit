"""
Tests for the executor class which runs and error cycles and optimizations.
The test are set out in
"""

import pytest
from openforcefield.topology import Molecule
from qcfractal.interface import FractalClient
from qcfractal.testing import fractal_compute_server
from qcsubmit.results import TorsionDriveCollectionResult
from qcsubmit.testing import temp_directory

from ..executor import Executor
from ..schema.fitting import FittingSchema
from ..utils import get_data
from .schema.test_fitting import get_fitting_schema


def test_optimizer_explicit():
    """
    Run the optimizer process in the main thread to make sure it works.
    """
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    # now make the schema
    schema = get_fitting_schema(molecules=ethane)
    result = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
    schema.update_with_results(results=result)
    # now submit to the executor
    execute = Executor()
    execute.fitting_schema = schema
    # we dont need the server here
    # put a task in the opt queue then kill it
    execute.total_tasks = 1
    execute.opt_queue.put(schema.molecules[0])
    with temp_directory():
        execute.optimizer()
        # find the task in the finished queue
        task = execute.finished_tasks.get()
        result_schema = execute.update_fitting_schema(task=task, fitting_schema=schema)
        smirks = result_schema.molecules[0].workflow[0].target_smirks
        # make sure they have been updated
        for smirk in smirks:
            for term in smirk.terms.values():
                assert float(term.k.split()[0]) != 1e-5


def test_restart_records(fractal_compute_server):
    """
    Make sure that the error cycle can restart a record and update the tasks when we hit an error.
    """

    client = FractalClient(fractal_compute_server)

    mol = Molecule.from_smiles("BrCO")
    schema = get_fitting_schema(molecules=mol)

    # make a server to submit the tasks to which will fail
    datasets = schema.generate_qcsubmit_datasets()

    # submit the torsiondrive which will fail
    datasets[0].metadata.long_description_url = "https://test.org"
    datasets[0].dataset_name = "restart testing"
    datasets[0].submit(client=client, ignore_errors=True)
    # wait for the errors
    fractal_compute_server.await_services()
    fractal_compute_server.await_results()

    executor = Executor()
    executor.activate_client(client=client)
    # generate the task map and queue
    executor.generate_dataset_task_map(datasets=datasets)
    executor.create_input_task_queue(fitting_schema=schema)
    task = schema.molecules[0]
    task_map = task.get_task_map()

    for task_hash, collection_tasks in task_map.items():
        spec = collection_tasks[0].entry.qc_spec
        entry_id, dataset_type, dataset_name = executor.task_map[task_hash]
        print("looking for ", entry_id, dataset_type, dataset_name)
        dataset = executor.client.get_collection(dataset_type, dataset_name)
        # get the record and the df index
        record, td_id = executor._get_record_and_index(dataset=dataset, spec=spec, record_name=entry_id)

        assert record is not None
        assert record.status.value == "ERROR"
        executor.restart_archive_record(record)
        # pull again
        record, td_id = executor._get_record_and_index(dataset=dataset, spec=spec, record_name=entry_id)
        assert record.status.value == "RUNNING"


def test_error_cycle_explicit(fractal_compute_server):
    """
    Run the error cycle in the main thread to make sure it does restart tasks correctly and keep track of the number of times this is attempted.
    Also make sure that a task status is moved to error when we exceed the retry limit.
    """

    client = FractalClient(fractal_compute_server)

    # get a molecule that will fail with ani
    mol = Molecule.from_smiles("BrCO")
    # now make the schema
    schema = get_fitting_schema(molecules=mol)

    executor = Executor()
    # register the client
    executor.activate_client(client=client)
    dataset = schema.generate_qcsubmit_datasets()[0]
    dataset.metadata.long_description_url = "https://test.org"
    dataset.dataset_name = "BrCO torsiondrive"
    # submit the dataset manually to ignore the errors
    dataset.submit(client=client, ignore_errors=True)
    # set up the executor manually
    executor.total_tasks = 1
    # lower the retry limit
    executor.max_retires = 1
    executor.fitting_schema = schema
    executor.generate_dataset_task_map(datasets=[dataset, ])

    # wait for the torsiondrive to finish
    fractal_compute_server.await_services()
    fractal_compute_server.await_results()

    # run the error cycle no 1
    executor._error_cycle_task(task=schema.molecules[0])
    # now get the tasks and update the schema
    task = executor.collection_queue.get()
    # make sure the task retries was incremented
    task_map = task.get_task_map()
    collection_stage = task_map["d263fc4d38661679402ca04d438435ee34b1c31f"][0].collection_stage
    assert collection_stage.retires == 1
    assert collection_stage.status.value == "COLLECTING"

    # task has been restarted so wait again
    fractal_compute_server.await_services()
    fractal_compute_server.await_results()

    # run again
    executor._error_cycle_task(task=task)
    # now pull the task out again
    task = executor.opt_queue.get()
    task_map = task.get_task_map()
    collection_stage = task_map["d263fc4d38661679402ca04d438435ee34b1c31f"][0].collection_stage
    assert collection_stage.retires == 1
    assert collection_stage.status.value == "ERROR"
    assert task.workflow[0].status.value == "ERROR"


def test_collecting_results(fractal_compute_server):
    """
    Make sure results are collected and a task is updated when finished.
    """

    client = FractalClient(fractal_compute_server)

    result = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
    # get ethane with the final converged geometries
    ethane = result.collection["[h:1][c:2]([h])([h])[c:3]([h:4])([h])[h]"].get_torsiondrive()
    schema = get_fitting_schema(ethane)
    # now submit to the executor
    executor = Executor()
    executor.total_tasks = 1

    # register the client
    executor.activate_client(client=client)
    dataset = schema.generate_qcsubmit_datasets()[0]
    dataset.metadata.long_description_url = "https://test.org"
    dataset.dataset_name = "CC torsiondrive"
    # submit the dataset manually to ignore the errors
    dataset.submit(client=client)

    # set up the executor manually
    executor.fitting_schema = schema
    executor.generate_dataset_task_map(datasets=[dataset, ])

    fractal_compute_server.await_services()
    fractal_compute_server.await_results()

    executor._error_cycle_task(task=schema.molecules[0])

    task = executor.opt_queue.get(timeout=5)
    opt = task.get_next_optimization_stage()
    assert opt.ready_for_fitting is True


def test_submit_new_tasks(fractal_compute_server):
    """
    Make sure that any new tasks which are generated/found are added to the archive instance.
    """

    client = FractalClient(fractal_compute_server)
    # build a molecule that will fail fast to save compute
    ethane = Molecule.from_smiles("CC")
    # now make the schema
    schema = get_fitting_schema(molecules=ethane)

    executor = Executor()
    # register the client
    executor.fitting_schema = schema
    executor.activate_client(client=client)

    # make sure new tasks are submitted
    task = schema.molecules[0]
    response = executor.submit_new_tasks(task=task)
    assert response == {'Bespokefit torsiondrives': {'ani2x': 1}}


def test_executor_no_collection():
    """
    Test using the executor when there are no tasks to collect only optimizations to run.
    """
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    # now make the schema
    schema = get_fitting_schema(molecules=ethane)
    result = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
    schema.update_with_results(results=result)

    # now submit to the executor
    execute = Executor()
    # there are no collection tasks
    assert execute.task_map == {}
    # submit the optimization
    with temp_directory():
        result_schema = execute.execute(fitting_schema=schema)
        # stop the server processes
        execute.server.stop()
        # make sure they are all finished
        assert execute.total_tasks == 0
        # check the results have been saved
        smirks = result_schema.molecules[0].workflow[0].target_smirks
        # make sure they have been updated
        for smirk in smirks:
            for term in smirk.terms.values():
                assert float(term.k.split()[0]) != 1e-5

        # now round load up the results
        schema = FittingSchema.parse_file("final_results.json.xz")
        # make sure all tasks are complete
        assert schema.molecules[0].get_next_optimization_stage() is None

    # clean up the server
    execute.server.stop()