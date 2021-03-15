import time
from multiprocessing import Process, Queue
from typing import Dict, List, Optional, Tuple, Union

from openff.qcsubmit.common_structures import QCSpec
from openff.qcsubmit.datasets import (
    BasicDataset,
    OptimizationDataset,
    TorsiondriveDataset,
)
from openff.qcsubmit.results import (
    BasicCollectionResult,
    OptimizationCollectionResult,
    TorsionDriveCollectionResult,
)
from qcfractal.interface import FractalClient
from qcfractal.interface.models.records import OptimizationRecord, ResultRecord
from qcfractal.interface.models.torsiondrive import TorsionDriveRecord

from openff.bespokefit.common_structures import Status
from openff.bespokefit.schema import FittingSchema, OptimizationSchema
from openff.bespokefit.utils import task_folder


class Executor:
    """
    This class executes a Fitting schema object, this involves working out what tasks to execute to collect reference data and what optimizations
    should be ran. While running QCArchive tasks this class will also handle basic error handling in the form of restarts.
    """

    def __init__(
        self,
        max_workers: int = 2,
        cores_per_worker: int = 2,
        memory_per_worker: int = 10,
        max_retries: int = 3,
    ) -> None:
        """
        Set up the executor data with dataset names and initial tasks which should be submitted.
        """
        self._dataset_name = "OpenFF Bespoke-fit"
        self._dataset_type_mapping = {
            "torsion1d": "torsiondrivedataset",
            "optimization": "optimizationdataset",
            "hessian": "dataset",
        }
        self.max_workers = max_workers
        self.cores_per_worker = cores_per_worker
        self.memory_per_worker = memory_per_worker
        # maybe let users set this for error cycling?
        self.max_retires: int = max_retries
        # keep track of the total number of molecules to be fit
        self.total_tasks = None
        # this is the error cycling queue
        self.collection_queue = Queue()
        # this is a queue for jobs ready to be optimized
        self.opt_queue = Queue()
        self.finished_tasks = Queue()
        self.task_map: Dict[str, str] = {}
        self.retries: Dict[str, int] = {}

    def execute(
        self, fitting_schema: FittingSchema, client: Optional[FractalClient] = None
    ) -> FittingSchema:
        """
        Execute a fitting schema using a snowflake qcfractal server. This involves generating QCSubmit datasets and error cycling them and then launching the forcebalance optimizations.


        Parameters:
            fitting_schema: The fitting schema that should be executed
            client: The fractal client we should connect to, if none then a snowflake will be used.

        Returns:
            The completed fitting schema this will contain any collected results including errors.
        """
        # keep track of the total number of molecules to be fit
        self.total_tasks = len(fitting_schema.tasks)
        # get the input datasets
        print("Searching for reference tasks")
        input_datasets = fitting_schema.generate_qcsubmit_datasets()
        if input_datasets:
            print("Reference tasks found generating input datasets")
            # now generate a mapping between the hash and the dataset entry
            print("generating task map")
            self.generate_dataset_task_map(datasets=input_datasets)
            print("connecting to qcfractal")
            server, client = self.activate_client(client=client)
            print("submitting new tasks")
            responses = self.submit_datasets(datasets=input_datasets, client=client)
            print("client response")
            print(responses)
        else:
            print("No reference tasks found... Not connecting to qcfractal")
            server, client = None, None
        print("generating collection task queue ...")
        # generate the initial task queue of collection tasks
        self.create_input_task_queue(fitting_schema=fitting_schema)
        print(f"task queue now contains tasks.")

        return self._execute(
            fitting_schema=fitting_schema, server=server, client=client
        )

    def _execute(
        self,
        fitting_schema: FittingSchema,
        server: Optional["FractalServer"],
        client: Optional[FractalClient],
    ) -> FittingSchema:
        print("starting main executor ...")
        # start the error cycle process
        jobs = []
        error_p = Process(target=self.error_cycle, args=(server, client))
        jobs.append(error_p)
        optimizer_p = Process(target=self.optimizer)
        jobs.append(optimizer_p)

        for job in jobs:
            job.start()

        # join them
        for job in jobs:
            job.join(timeout=5)

        print("starting to collect finished tasks")
        while True:
            # here we need to watch for results on the parent process
            print("collecting complete tasks...")
            task = self.finished_tasks.get()
            print("Found a complete task")
            fitting_schema = self.update_fitting_schema(
                task=task, fitting_schema=fitting_schema
            )
            print("tasks to do ", self.total_tasks)
            self.total_tasks -= 1
            print("tasks left", self.total_tasks)
            if self.total_tasks == 0:
                print("breaking out of task updates")
                break

        print("all tasks done exporting to file.")
        fitting_schema.export_schema("final_results.json.xz")
        return fitting_schema

    def activate_client(
        self,
        client: Optional[FractalClient],
    ) -> Tuple["FractalServer", FractalClient]:
        """
        Activate the connection to the chosen qcarchive instance or spin up a snowflake when requested.

        Parameters
        ----------

        Notes
        -----
            This can be a snowflake server or a local qcarchive instance error cycling should still work.
        """
        if isinstance(client, FractalClient):
            # we can not get the server from the client instance so we just get info
            return client.server_information(), client
        else:
            from qcfractal import FractalSnowflake

            # TODO fix to spin up workers with settings
            server = FractalSnowflake(max_workers=self.max_workers)
            print(server)
            client = server.client()

            return server, client

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
                self.task_map[entry.attributes.task_hash] = entry.index

    def create_input_task_queue(self, fitting_schema: FittingSchema) -> None:
        """
        Create a task for each molecule in fitting schema and enter them into the collection queue.
        """
        for task in fitting_schema.tasks:
            self.collection_queue.put(task)

    def submit_datasets(
        self,
        datasets: List[Union[BasicDataset, OptimizationDataset, TorsiondriveDataset]],
        client: FractalClient,
    ) -> Dict[str, Dict[str, int]]:
        """
        Submit the initial datasets to the qcarchive instance and return the response from the server.

        Parameters:
            datasets: The QCSubmit style datasets which are to be submitted.
            client

        """

        responses = {}
        for dataset in datasets:
            # make sure there is a molecule in the dataset
            if dataset.n_molecules > 0:
                response = dataset.submit(client=client)
                responses[dataset.dataset_name] = response

        return responses

    def get_record(self, dataset, spec: QCSpec, record_name: str):
        """
        Find a record and its dataset index used for result collection.
        This abstracts accessing all dataset types into one function.
        """
        # TODO add support for basic datasets
        try:
            record = dataset.get_record(record_name, spec.spec_name)
            return record
        except KeyError:
            pass

        return None, None

    def _error_cycle_task(
        self, task: OptimizationSchema, client: FractalClient
    ) -> None:
        """
        Specific error cycling for a given task.
        """

        print("task molecule name ", task.job_id)
        # keep track of any records that should be collected
        to_collect = {"torsion1d": {}, "optimization": {}, "hessian": {}}
        # loop through each target and loop for tasks to update
        for target in task.targets:
            # get the dataset
            dataset = client.get_collection(
                collection_type=self._dataset_type_mapping[target.collection_workflow],
                name=self._dataset_name,
            )
            # now update each entry
            for entry in target.tasks:
                # now for each one we want to query the archive and their status
                task_hash = entry.get_task_hash()
                entry_id = self.task_map[task_hash]
                print("pulling record for ", entry_id)
                record = self.get_record(
                    dataset=dataset, spec=target.qc_spec, record_name=entry_id
                )
                if record.status.value == "COMPLETE":
                    collection_set = to_collect[target.collection_workflow]
                    collection_set.setdefault(target.qc_spec.spec_name, []).append(
                        entry_id
                    )
                elif record.status.value == "ERROR":
                    # save the error into the task
                    task.error_message = record.get_error()
                    print(
                        f"The task {task.job_id} has errored with attempting restart. Error message:",
                        task.error_message,
                    )
                    # update the restart count
                    if task_hash not in self.retries:
                        self.retries[task_hash] = 1
                    else:
                        self.retries[task_hash] += 1
                    if self.retries[task_hash] == self.max_retires:
                        # mark as errored
                        task.status = Status.CollectionError
                    else:
                        # restart the job
                        self.restart_archive_record(task=record, client=client)
                        task.status = Status.ErrorCycle
                else:
                    # the task is incomplete let it run
                    continue

        # if we have values to collect update the task here
        if any(to_collect.values()):
            print("collecting results for ", to_collect)
            self.collect_task_results(task, to_collect, client)

        # now we should look for new tasks to submit
        print("looking for new reference tasks ...")
        if task.get_task_map():
            response = self.submit_new_tasks(task, client=client)
            print("response of new tasks ... ", response)

        print("checking for optimizations to run ...")
        if task.ready_for_fitting:
            # the molecule is done pas to the opt queue to be removed
            self.opt_queue.put(task)

        elif task.status == Status.CollectionError:
            # one of the collection entries has filed so pass to opt which will fail
            self.opt_queue.put(task)
        else:
            print("task not finished putting back into the queue.")
            # the molecule is not finished and not ready for opt error cycle again
            self.collection_queue.put(task)

    def error_cycle(self, server: "FractalSever", client: FractalClient) -> None:
        """
        For the given MoleculeSchema check that all collection tasks are running and error cycle jobs. Will also generate new collection tasks as needed
        for example hessian tasks are created when optimizations are finished.
        #TODO this should be a function which can give the server if not started
        """

        while True:
            print("pulling task from collection queue")
            task = self.collection_queue.get()
            if isinstance(task, str):
                print("the collection queue is ending now")
                # this is the kill message so kill the worker
                # try and kill the server if it is a snowflake
                try:
                    server.stop()
                except AttributeError:
                    pass
                break
            elif task.ready_for_fitting:
                self.opt_queue.put(task)

            else:
                self._error_cycle_task(task=task, client=client)

            time.sleep(20)

    def collect_task_results(
        self, task: OptimizationSchema, collection_dict: Dict, client: FractalClient
    ):
        """
        Gather the results in the collection dict and update the task with them.
        """
        results = self.collect_results(record_map=collection_dict, client=client)
        for result in results:
            task.update_with_results(results=result)

    def update_fitting_schema(
        self, task: OptimizationSchema, fitting_schema: FittingSchema
    ) -> FittingSchema:
        """
        Update the given task back into the fitting schema so we can keep track of progress.
        Call this after any result or optimization update.
        """
        for i, molecule_task in enumerate(fitting_schema.tasks):
            if task.job_id == molecule_task.job_id:
                print("updating task")
                # update the schema and break
                fitting_schema.tasks[i] = task
                return fitting_schema

    def submit_new_tasks(
        self, task: OptimizationSchema, client: FractalClient
    ) -> Dict[str, Dict[str, int]]:
        """
        For the given molecule schema query it for new tasks to submit and either add them to qcarchive or put them in the
        local task queue.
        """
        datasets = task.build_qcsubmit_datasets()
        # now all tasks have been put into the dataset even those running
        # remove a hash that has been seen before
        # add new tasks to the hash record
        for dataset in datasets:
            to_remove = []
            for task_id, entry in dataset.dataset.items():
                task_hash = entry.attributes.task_hash
                if task_hash in self.task_map:
                    to_remove.append(task_id)
                else:
                    self.task_map[task_hash] = entry.index
            # now loop over the records to remove
            if to_remove:
                for entry_id in to_remove:
                    del dataset.dataset[entry_id]

        # now submit the datasets
        return self.submit_datasets(datasets=datasets, client=client)

    def collect_results(
        self,
        record_map: Dict[str, Dict[str, Dict[str, List[str]]]],
        client: FractalClient,
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
            "hessian": BasicCollectionResult,
            "optimization": OptimizationCollectionResult,
            "torsion1d": TorsionDriveCollectionResult,
        }
        results = []
        for dataset_type, records in record_map.items():
            # get the result class
            result_type = dataset_types[dataset_type.lower()]
            for spec_name, entries in records.items():
                result = result_type.from_server(
                    client=client,
                    dataset_name=self._dataset_name,
                    subset=entries,
                    spec_name=spec_name,
                )
                results.append(result)

        return results

    def restart_archive_record(
        self,
        task: Union[ResultRecord, OptimizationRecord, TorsionDriveRecord],
        client: FractalClient,
    ) -> None:
        """
        Take a record and dispatch the type of restart to be done.
        """
        if task.__class__ == ResultRecord:
            print("restarting basic ...")
            self.restart_basic(
                [
                    task.id,
                ],
                client=client,
            )
        elif task.__class__ == OptimizationRecord:
            print("restarting optimizations ...")
            self.restart_optimizations(
                [
                    task.id,
                ],
                client=client,
            )
        else:
            print("restarting torsiondrives and optimizations ...")
            # we need the optimization ids first
            td_opts = []
            for optimizations in task.optimization_history.values():
                td_opts.extend(optimizations)
            # now query the optimizations
            opt_records = client.query_procedures(td_opts)
            restart_opts = [opt.id for opt in opt_records if opt.status == "ERROR"]
            # restart opts then torsiondrives
            self.restart_optimizations(restart_opts, client=client)
            self.restart_torsiondrives(
                [
                    task.id,
                ],
                client=client,
            )

    def restart_torsiondrives(
        self, torsiondrive_ids: List[int], client: FractalClient
    ) -> None:
        """
        Restart all torsiondrive records.
        """
        for td in torsiondrive_ids:
            client.modify_services("restart", procedure_id=td)

    def restart_optimizations(
        self, optimization_ids: List[int], client: FractalClient
    ) -> None:
        """
        Restart all optimizations.
        """
        for opt in optimization_ids:
            client.modify_tasks(operation="restart", base_result=opt)

    def restart_basic(self, basic_ids: List[int], client: [FractalClient]) -> None:
        """
        Restart all basic single point tasks.
        """
        pass

    def optimizer(self) -> None:
        """
        Monitors the optimizer queue and runs any tasks that arrive in the list.
        """
        import warnings

        sent_tasks = 0
        while True:
            print("looking for task in queue")
            task: OptimizationSchema = self.opt_queue.get()
            print("found optimizer task for ", task.job_id)
            # move into the task folder
            with task_folder(folder_name=task.job_id):
                # make sure it is ready for fitting
                if task.ready_for_fitting:
                    # now we need to set up the optimizer
                    print("preparing to optimize")
                    optimizer = task.get_optimizer()
                    # remove any tasks
                    optimizer.clear_optimization_targets()
                    print("sending task for optimization")
                    result = optimizer.optimize(schema=task)
                    if result.status == Status.ConvergenceError:
                        warnings.warn(
                            f"The optimization {result.job_id} failed to converge the best results were still collected.",
                            UserWarning,
                        )
                    # check for running QM tasks
                    if task.get_task_map():
                        print("putting back into collect queue")
                        # submit to the collection queue again
                        self.collection_queue.put(task)
                    else:
                        # the task is finished so send it back
                        print("Finished task")
                        self.finished_tasks.put(task)
                        sent_tasks += 1
                else:
                    # the task has an error so fail it
                    self.finished_tasks.put(task)
                    sent_tasks += 1

                # kill condition
                if sent_tasks == self.total_tasks:
                    print("killing workers")
                    self.collection_queue.put("END")
                    break
