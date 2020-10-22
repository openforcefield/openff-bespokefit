import time
from multiprocessing import Process, Queue
from typing import Dict, List, Optional, Tuple, Union

from qcfractal.interface import FractalClient
from qcfractal.interface.models.records import OptimizationRecord, ResultRecord
from qcfractal.interface.models.torsiondrive import TorsionDriveRecord
from qcsubmit.common_structures import QCSpec
from qcsubmit.datasets import BasicDataset, OptimizationDataset, TorsiondriveDataset
from qcsubmit.procedures import GeometricProcedure
from qcsubmit.results import (
    BasicCollectionResult,
    OptimizationCollectionResult,
    TorsionDriveCollectionResult,
)

from .common_structures import Status
from .schema.fitting import FittingSchema, MoleculeSchema
from .utils import schema_to_datasets


class Executor:
    """
    This class executes a Fitting schema object, this involves working out what tasks to execute to collect reference data and what optimizations
    should be ran. While running QCArchive tasks this class will also handle basic error handling in the form of restarts.
    """

    def __init__(self, max_workers: int = 4, max_retries: int = 3) -> None:
        """
        Set up the executor data with dataset names and initial tasks which should be submitted.
        """
        self.client = None
        self.server = None
        self.max_workers = max_workers
        # activate the client and server
        self.fitting_schema = None
        self._torsion_dataset: Optional[str] = None
        self._optimization_dataset: Optional[str] = None
        self._energy_dataset: Optional[str] = None
        self._gradient_dataset: Optional[str] = None
        self._hessian_dataset: Optional[str] = None
        self._optimizer_settings = None
        # keep track of the total number of molecules to be fit
        self.total_tasks = None
        # maybe let users set this for error cycling?
        self.max_retires: int = max_retries
        # this is the error cycling queue
        self.collection_queue = Queue()
        # this is a queue for jobs ready to be optimized
        self.opt_queue = Queue()
        self.finished_tasks = Queue()
        self.task_map: Dict[str, Tuple[str, str, str]] = {}
        # bump the maxiter for ani optimizations to help convergence
        self.geometric_settings: Optional[GeometricProcedure] = GeometricProcedure(
            maxiter=1000
        )

    def execute(
        self, fitting_schema: FittingSchema, client: Optional[FractalClient] = None
    ) -> FittingSchema:
        """
        Execute a fitting schema. This involves generating QCSubmit datasets and error cycling them and then launching the forcebalance optimizations.


        Parameters:
            fitting_schema: The fitting schema that should be executed
            client: Optional fractal client already connected if None we attempt to make a client using the details in the fitting schema.

        Returns:
            The completed fitting schema this will contain any collected results including errors.
        """
        # activate the client and server
        self.activate_client(
            client=client or fitting_schema.client, workers=self.max_workers
        )
        # set up the dataset names for error cycling
        self._torsion_dataset: str = fitting_schema.torsiondrive_dataset_name
        self._optimization_dataset: str = fitting_schema.optimization_dataset_name
        self._energy_dataset: str = fitting_schema.singlepoint_dataset_name + " energy"
        self._gradient_dataset: str = (
            fitting_schema.singlepoint_dataset_name + " gradient"
        )
        self._hessian_dataset = fitting_schema.singlepoint_dataset_name + " hessain"
        self._optimizer_settings = fitting_schema.optimizer_settings
        self.fitting_schema = fitting_schema

        # keep track of the total number of molecules to be fit
        self.total_tasks = len(fitting_schema.molecules)
        # get the input datasets
        print("making qcsubmit datasets")
        input_datasets = fitting_schema.generate_qcsubmit_datasets(
            geometric_settings=self.geometric_settings
        )
        # now generate a mapping between the hash and the dataset entry
        print("generating task map")
        self.generate_dataset_task_map(datasets=input_datasets)
        print("generating collection task queue ...")
        # generate the initial task queue of collection tasks
        self.create_input_task_queue(fitting_schema=fitting_schema)
        print(f"task queue now contains tasks.")
        if client is None:
            # if the client is live some tasks might already be present so dont submit the dataset
            print("starting job submission")
            responses = self.submit_datasets(datasets=input_datasets)
            print("client response")
            print(responses)

        return self._execute(fitting_schema=fitting_schema)

    def _execute(self, fitting_schema: FittingSchema) -> FittingSchema:
        print("starting main executor ...")
        # start the error cycle process
        error_p = Process(target=self.error_cycle)
        error_p.start()
        optimizer_p = Process(target=self.optimizer)
        optimizer_p.start()

        # join them
        error_p.join()
        optimizer_p.join()
        while True:
            # here we need to watch for results on the parent process
            task = self.finished_tasks.get()
            fitting_schema = self.update_fitting_schema(
                task=task, fitting_schema=fitting_schema
            )
            self.total_tasks -= 1
            if self.total_tasks == 0:
                break
        print("all tasks done exporting to file.")
        fitting_schema.export_schema("final_results.json.xz")
        return fitting_schema

    def activate_client(self, client: str, workers: int = 4) -> None:
        """
        Activate the connection to the chosen qcarchive instance.

        Parameters
        ----------
        client: str
            A string of the client name for example snowflake will launch a local snowflake instance. This can
                be the file name which contains login details which can be passed to FractalClient.
        workers: int
            If this is a snowflake worker this will be the number of workers used.

        Notes
        -----
            This can be a snowflake server or a local qcarchive instance error cycling should still work.
        """
        from qcfractal import FractalSnowflake, FractalSnowflakeHandler
        from qcfractal.interface import FractalClient

        if isinstance(client, FractalClient):
            self.client = client
            self.server = client.server_information()
        elif client.lower() == "snowflake_notebook":
            self.server = FractalSnowflakeHandler()
            self.client = self.server.client()
        elif client.lower() == "snowflake":
            self.server = FractalSnowflake(max_workers=workers)
            self.client = self.server.client()
        else:
            self.client = FractalClient.from_file(client)
            self.server = self.client.server_information()

    def generate_dataset_task_map(
        self,
        datasets: List[Union[BasicDataset, OptimizationDataset, TorsiondriveDataset]],
    ) -> None:
        """
        Generate mapping between all of the current tasks in the datasets and their entries updates self.

        Parameters:
            datasets: A list of the qcsubmit datasets which contain tasks to be computed.
        """

        for dataset in datasets:
            for entry in dataset.dataset.values():
                self.task_map[entry.attributes["task_hash"]] = (
                    entry.index,
                    dataset.dataset_type.lower(),
                    dataset.dataset_name,
                )

    def create_input_task_queue(self, fitting_schema: FittingSchema) -> None:
        """
        Create a task for each molecule in fitting schema and enter them into the collection queue.
        """
        for molecule in fitting_schema.molecules:
            self.collection_queue.put(molecule)

    def submit_datasets(
        self,
        datasets: List[Union[BasicDataset, OptimizationDataset, TorsiondriveDataset]],
    ) -> Dict[str, Dict[str, int]]:
        """
        Submit the initial datasets to the qcarchive instance and return the response from the server.

        Parameters:
            datasets: The QCSubmit style datasets which are to be submitted.
        """

        responses = {}
        for dataset in datasets:
            # make sure there is a molecule in the dataset
            if dataset.n_molecules > 0:
                # make sure the metadata is complete
                dataset.metadata.long_description_url = (
                    "https://github.com/openforcefield/bespoke-fit"
                )
                response = dataset.submit(client=self.client)
                responses[dataset.dataset_name] = response

        return responses

    def _get_record_and_index(self, dataset, spec: QCSpec, record_name: str):
        """
        Find a record and its dataset index used for result collection.
        """
        try:
            record = dataset.get_record(record_name, spec.spec_name)
            # loop over the index
            for td_index, td_entry in dataset.data.records.items():
                if td_entry.name == record_name:
                    return record, td_index
        except KeyError:
            pass

        return None, None

    def _update_status(self, collection_tasks, record, task):
        """
        Update the collection tasks status with the record progress and the overall task progress.
        """
        # error cycle
        if record.status.value == "ERROR":
            if collection_tasks[0].collection_stage.retires < self.max_retires:
                # we should restart the task here
                print("restarting the record")
                self.restart_archive_record(record)
                # now increment the restart counter
                for collection_task in collection_tasks:
                    collection_task.collection_stage.retires += 1
                    collection_task.collection_stage.status = Status.Collecting
            else:
                for collection_task in collection_tasks:
                    collection_task.collection_stage.status = Status.Error
        # normal execution
        elif record.status.value == "RUNNING":
            for collection_task in collection_tasks:
                collection_task.collection_stage.status = Status.Collecting

        elif record.status.value == "COMPLETE":
            # now we need to save the results
            for collection_task in collection_tasks:
                collection_task.collection_stage.status = Status.Complete

        # now update the opt stage
        for opt_stage in task.workflow:
            for target in opt_stage.targets:
                for entry in target.entries:
                    for task in entry.current_tasks():
                        if task.status == Status.Error:
                            opt_stage.status = Status.Error

    def _error_cycle_task(self, task) -> None:
        """
        Specific error cycling for a given task.
        """

        print("task molecule name ", task.molecule)

        # first we have to get all of the tasks for this molecule
        task_map = task.get_task_map()

        to_collect = {
            "dataset": {},
            "optimizationdataset": {},
            "torsiondrivedataset": {},
        }
        # now for each one we want to query the archive and their status
        for task_hash, collection_tasks in task_map.items():
            spec = collection_tasks[0].entry.qc_spec
            entry_id, dataset_type, dataset_name = self.task_map[task_hash]
            print("looking for ", entry_id, dataset_type, dataset_name)
            dataset = self.client.get_collection(dataset_type, dataset_name)
            # get the record and the df index
            record, td_id = self._get_record_and_index(
                dataset=dataset, spec=spec, record_name=entry_id
            )

            # if the record is not found the job has not been generated yet
            if record is not None:
                print("updating the status")
                self._update_status(collection_tasks, record, task)
                print(collection_tasks[0])
                if collection_tasks[0].collection_stage.status == Status.Complete:
                    try:
                        to_collect[dataset_type][dataset_name].setdefault(
                            spec.spec_name, []
                        ).append(td_id)
                    except KeyError:
                        to_collect[dataset_type][dataset_name] = {
                            spec.spec_name: [
                                td_id,
                            ]
                        }

        # if we have values to collect update the task here
        if any(to_collect.values()):
            print("collecting results for ", to_collect)
            self._collect_task_results(task, to_collect)

        # now we should look for new tasks to submit
        print("looking for new tasks ...")
        if task.get_task_map():
            response = self.submit_new_tasks(task)
            print("response of new tasks ... ", response)

        print("checking for optimizations to run ...")
        opt = task.get_next_optimization_stage()
        if opt is None:
            # the molecule is done pas to the opt queue to be removed
            self.opt_queue.put(task)
        elif opt.ready_for_fitting:
            print(" found optimization submitting for task", task.molecule)
            self.opt_queue.put(task)
        elif opt.status == Status.Error:
            # one of the collection entries has filed so pass to opt which will fail
            self.opt_queue.put(task)
        else:
            print("task not finished putting back into the queue.")
            # the molecule is not finished and not ready for opt error cycle again
            self.collection_queue.put(task)

    def error_cycle(self) -> None:
        """
        For the given MoleculeSchema check that all collection tasks are running and error cycle jobs. Will also generate new collection tasks as needed
        for example hessian tasks are created when optimizations are finished.

        """

        while True:
            print("pulling task from collection queue")
            task = self.collection_queue.get()
            if isinstance(task, str):
                # this is the kill message so kill the worker
                break
            else:
                self._error_cycle_task(task=task)
                time.sleep(20)

    def _collect_task_results(self, task: MoleculeSchema, collection_dict: Dict):
        """
        Gather the results in the collection dict and update the task with them.
        """
        results = self.collect_results(record_map=collection_dict)
        task.update_with_results(results=results)

    def update_fitting_schema(
        self, task: MoleculeSchema, fitting_schema: FittingSchema
    ) -> FittingSchema:
        """
        Update the given task back into the fitting schema so we can keep track of progress.
        Call this after any result or optimization update.
        """
        for i, molecule_task in enumerate(fitting_schema.molecules):
            if task == molecule_task:
                print("updating task")
                # update the schema and break
                fitting_schema.molecules[i] = task
                return fitting_schema

    def submit_new_tasks(self, task: MoleculeSchema) -> Dict[str, Dict[str, int]]:
        """
        For the given molecule schema query it for new tasks to submit and either add them to qcarchive or put them in the
        local task queue.
        """
        datasets = schema_to_datasets(
            [
                task,
            ],
            singlepoint_name=self.fitting_schema.singlepoint_dataset_name,
            optimization_name=self.fitting_schema.optimization_dataset_name,
            torsiondrive_name=self.fitting_schema.torsiondrive_dataset_name,
            geometric_options=self.geometric_settings,
        )
        # now all tasks have been put into the dataset even those running
        # remove a hash that has been seen before
        # add new tasks to the hash record

        for dataset in datasets:
            to_remove = []
            for task_id, entry in dataset.dataset.items():
                task_hash = entry.attributes["task_hash"]
                if task_hash in self.task_map:
                    to_remove.append(task_id)
                else:
                    self.task_map[task_hash] = (
                        entry.index,
                        dataset.dataset_type.lower(),
                        dataset.dataset_name,
                    )
            # now loop over the records to remove
            if to_remove:
                for entry_id in to_remove:
                    del dataset.dataset[entry_id]

        # now submit the datasets
        return self.submit_datasets(datasets)

    def collect_results(
        self, record_map: Dict[str, Dict[str, Dict[str, List[str]]]]
    ) -> List[
        Union[
            BasicCollectionResult,
            OptimizationCollectionResult,
            TorsionDriveCollectionResult,
        ]
    ]:
        """
        For the given list of record ids per dataset type collect all of the results.
        """
        dataset_types = {
            "dataset": BasicCollectionResult,
            "optimizationdataset": OptimizationCollectionResult,
            "torsiondrivedataset": TorsionDriveCollectionResult,
        }
        results = []
        for dataset_type, collection in record_map.items():
            # get the result class
            result_type = dataset_types[dataset_type.lower()]
            for dataset_name, spec_data in collection.items():
                for spec, records in spec_data.items():
                    result = result_type.from_server(
                        client=self.client,
                        dataset_name=dataset_name,
                        subset=records,
                        spec_name=spec,
                    )
                    results.append(result)

        return results

    def restart_archive_record(
        self, task: Union[ResultRecord, OptimizationRecord, TorsionDriveRecord]
    ) -> None:
        """
        Take a record and dispatch the type of restart to be done.
        """
        if isinstance(task, ResultRecord):
            print("restarting basic ...")
            self.restart_basic(
                [
                    task.id,
                ]
            )
        elif isinstance(task, OptimizationRecord):
            print("restarting optimizations ...")
            self.restart_optimizations(
                [
                    task.id,
                ]
            )
        else:
            print("restarting torsiondrives and optimizations ...")
            # we need the optimization ids first
            td_opts = []
            for optimizations in task.optimization_history.values():
                td_opts.extend(optimizations)
            # now query the optimizations
            opt_records = self.client.query_procedures(td_opts)
            restart_opts = [opt.id for opt in opt_records if opt.status == "ERROR"]
            # restart opts then torsiondrives
            self.restart_optimizations(restart_opts)
            self.restart_torsiondrives(
                [
                    task.id,
                ]
            )

    def restart_torsiondrives(self, torsiondrive_ids: List[int]) -> None:
        """
        Restart all torsiondrive records.
        """
        for td in torsiondrive_ids:
            self.client.modify_services("restart", procedure_id=td)

    def restart_optimizations(self, optimization_ids: List[int]) -> None:
        """
        Restart all optimizations.
        """
        for opt in optimization_ids:
            self.client.modify_tasks(operation="restart", base_result=opt)

    def restart_basic(self, basic_ids: List[int]) -> None:
        """
        Restart all basic single point tasks.
        """
        pass

    def optimizer(self) -> None:
        """
        Monitors the optimizer queue and runs any tasks that arrive in the list.
        """
        sent_tasks = 0
        while True:
            print("looking for task in queue")
            task = self.opt_queue.get()
            print("found optimizer task for ", task.molecule)
            # now get the opt
            opt = task.get_next_optimization_stage()
            # make sure it is ready
            if opt is not None and opt.ready_for_fitting:
                # now we need to set up the optimizer
                optimizer = self.fitting_schema.get_optimizer(opt.optimizer_name)
                # remove any tasks
                optimizer.clear_optimization_targets()
                result = optimizer.optimize(
                    workflow=opt, initial_forcefield=task.initial_forcefield
                )
                # now we need to update the workflow stage with the result
                print("applying results ...")
                print("current task workflow ...")
                task.update_optimization_stage(result)
                # check for running QM tasks
                if task.get_task_map():
                    # submit to the collection queue again
                    self.collection_queue.put(task)
                elif task.get_next_optimization_stage() is not None:
                    # we have another task to optimize so put back into the queue for collection
                    self.opt_queue.put(task)
                else:
                    # the task is finished so send it back
                    self.finished_tasks.put(task)
                    sent_tasks += 1
            else:
                # the task has an error so fail it
                self.finished_tasks.put(task)
                sent_tasks += 1
            # kill condition
            if sent_tasks == self.total_tasks:
                self.collection_queue.put("END")
                break
