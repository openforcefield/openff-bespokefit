import logging
import time
from multiprocessing import Process, Queue
from typing import TYPE_CHECKING, Collection, Dict, List, Optional, Tuple, Union

from openff.qcsubmit.common_structures import QCSpec
from openff.qcsubmit.datasets import (
    BasicDataset,
    OptimizationDataset,
    TorsiondriveDataset,
)
from openff.qcsubmit.results import (
    BasicResultCollection,
    OptimizationResultCollection,
    TorsionDriveResultCollection,
)
from openff.qcsubmit.serializers import serialize
from qcportal import FractalClient
from qcportal.models import ObjectId
from qcportal.models.records import OptimizationRecord, ResultRecord
from qcportal.models.torsiondrive import TorsionDriveRecord

from openff.bespokefit.optimizers import get_optimizer
from openff.bespokefit.schema.data import BespokeQCData
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema, Status
from openff.bespokefit.schema.results import BespokeOptimizationResults

if TYPE_CHECKING:
    from qcfractal import FractalServer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

QCResultCollection = Union[
    TorsionDriveResultCollection,
    OptimizationResultCollection,
    BasicResultCollection,
]


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
        keep_files: bool = True,
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
        self.keep_files = keep_files
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
        self,
        *optimizations: BespokeOptimizationSchema,
        client: Optional[FractalClient] = None,
    ) -> List[BespokeOptimizationResults]:
        """
        Execute a fitting schema using a snowflake qcfractal server. This involves generating QCSubmit datasets and error cycling them and then launching the forcebalance optimizations.


        Parameters:
            optimizations: The bespoke optimization tasks that should be executed
            client: The fractal client we should connect to, if none then a snowflake will be used.

        Returns:
            The completed fits optimizations will contain any collected results including errors.
        """

        if not all(
            isinstance(optimization, BespokeOptimizationSchema)
            for optimization in optimizations
        ):
            raise RuntimeError("Only bespoke optimization schemas can be executed.")

        if len(optimizations) == 0:
            return []

        # keep track of the total number of molecules to be fit
        self.total_tasks = len(optimizations)

        # get the input datasets
        logger.info("Searching for reference tasks")

        input_datasets_per_type = {}

        for optimization in optimizations:

            for dataset in optimization.build_qcsubmit_datasets():

                if dataset.type not in input_datasets_per_type:

                    input_datasets_per_type[dataset.type] = dataset
                    continue

                input_datasets_per_type[dataset.type] += dataset

        input_datasets = [*input_datasets_per_type.values()]

        if len(input_datasets) > 0:
            logger.info("Reference tasks found generating input QCSubmit datasets")
            # now generate a mapping between the hash and the dataset entry
            logger.debug("Generating task map")
            self.generate_dataset_task_map(datasets=input_datasets)
            server, client = self.activate_client(client=client)
            logger.info(f"Connected to QCFractal with address {client.address}")
            logger.info("Submitting tasks to the queue")
            responses = self.submit_datasets(datasets=input_datasets, client=client)
            logger.info(f"The client response {responses}")
        else:
            logger.info("No reference tasks found. Not connecting to QCFractal")
            server, client = None, None
        logger.info("Generating Bespokefit task queue")
        # generate the initial task queue of collection tasks
        self.create_input_task_queue(optimizations)
        logger.debug("Queue now contains tasks")

        return self._execute(server=server, client=client)

    def _execute(
        self,
        server: Optional["FractalServer"],
        client: Optional[FractalClient],
    ) -> List[BespokeOptimizationResults]:

        logger.info("Starting main executor")
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

        logger.info("Waiting for finished tasks")
        task_results = []

        while True:
            # here we need to watch for results on the parent process
            task_result = self.finished_tasks.get()
            task_results.append(task_result)
            serialize(
                {
                    result.input_schema.id: result.json(indent=2)
                    for result in task_results
                },
                file_name="final_results.json.xz",
            )
            self.total_tasks -= 1
            logger.info(f"Tasks left {self.total_tasks}")
            if self.total_tasks == 0:
                logger.info("All tasks finished shutting down...")
                break

        logger.info("All tasks done exporting to file.")
        serialize(
            {result.input_schema.id: result.json(indent=2) for result in task_results},
            file_name="final_results.json.xz",
        )
        return task_results

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

            print("building new snowflake")

            # TODO fix to spin up workers with settings
            server = FractalSnowflake(max_workers=self.max_workers)
            client = server.client()

            return server, client

    def generate_dataset_task_map(
        self,
        datasets: List[Union[BasicDataset, OptimizationDataset, TorsiondriveDataset]],
    ):
        """
        Generate mapping between all of the current tasks in the datasets and their entries updates self.

        Parameters:
            datasets: A list of the qcsubmit datasets which contain tasks to be computed.
        """

        for dataset in datasets:
            for entry in dataset.dataset.values():
                self.task_map[entry.attributes.task_hash] = entry.index

    def create_input_task_queue(
        self, optimizations: Collection[BespokeOptimizationSchema]
    ):
        """Enter each optimization into the collection queue."""

        for optimization in optimizations:
            self.collection_queue.put(optimization)

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
        self, task: BespokeOptimizationSchema, client: FractalClient
    ) -> None:
        """
        Specific error cycling for a given task.
        """

        logger.info(f"Error cycling task with id {task.id}")
        # keep track of any records that should be collected
        to_collect = {"torsion1d": {}, "optimization": {}, "hessian": {}}
        # loop through each target and loop for tasks to update
        restart_cap = False
        for target in task.targets:

            if not isinstance(target.reference_data, BespokeQCData):
                # Skip existing QC data sets.
                continue

            # get the dataset
            dataset = client.get_collection(
                collection_type=self._dataset_type_mapping[target.bespoke_task_type()],
                name=self._dataset_name,
            )
            # now update each entry
            for entry in target.reference_data.tasks:
                # now for each one we want to query the archive and their status
                task_hash = entry.get_task_hash()
                entry_id = self.task_map[task_hash]
                record = self.get_record(
                    dataset=dataset,
                    spec=target.reference_data.qc_spec,
                    record_name=entry_id,
                )
                if record.status.value == "COMPLETE":
                    collection_set = to_collect[target.bespoke_task_type()]
                    collection_set.setdefault(
                        target.reference_data.qc_spec.spec_name, []
                    ).append(entry_id)
                elif record.status.value == "ERROR":
                    # save the error into the task
                    task.error_message = record.get_error()
                    logger.warning(
                        f"The task {task.id} has errored, attempting restart. Error message {task.error_message}"
                    )
                    # update the restart count
                    if task_hash not in self.retries:
                        self.retries[task_hash] = 1
                    else:
                        self.retries[task_hash] += 1
                    if self.retries[task_hash] < self.max_retires:
                        # restart the job
                        self.restart_archive_record(task=record, client=client)
                    else:
                        # we have hit the restart cap so remove the task
                        restart_cap = True
                else:
                    # the task is incomplete let it run
                    continue

        # if we have values to collect update the task here
        if any(to_collect.values()):
            logger.info("Collecting complete QCFractal data")
            self.collect_task_results(task, to_collect, client)

        # now we should look for new tasks to submit
        logger.info("Looking for new QCFractal tasks to submit")
        if task.get_task_map():
            response = self.submit_new_tasks(task, client=client)
            logger.info(f"New tasks submitted with response {response}")

        logger.info("Checking for new optimization tasks")
        if task.ready_for_fitting:
            # the molecule is done pas to the opt queue to be removed
            self.opt_queue.put(task)

        elif restart_cap:
            # one of the collection entries has failed so pass to opt which will fail
            logger.warning(
                f"A task with id {task.id} has failed {self.max_retires} times and is being removed"
            )
            self.opt_queue.put(task)
        else:
            logger.info(f"Task with id {task.id} is still running")
            # the molecule is not finished and not ready for opt error cycle again
            self.collection_queue.put(task)

    def error_cycle(self, server: "FractalServer", client: FractalClient) -> None:
        """
        For the given MoleculeSchema check that all collection tasks are running and error cycle jobs. Will also generate new collection tasks as needed
        for example hessian tasks are created when optimizations are finished.
        #TODO this should be a function which can give the server if not started
        """

        while True:
            logger.info("Searching for QCFractal task")
            task = self.collection_queue.get()
            if isinstance(task, str):
                logger.info("QCFactal queue complete")
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
        self,
        optimization: BespokeOptimizationSchema,
        collection_dict: Dict,
        client: FractalClient,
    ):
        """
        Gather the results in the collection dict and update the task with them.
        """
        results = self.collect_results(record_map=collection_dict, client=client)
        for result in results:
            optimization.update_with_results(results=result.to_records())

    def submit_new_tasks(
        self, optimization: BespokeOptimizationSchema, client: FractalClient
    ) -> Dict[str, Dict[str, int]]:
        """
        For the given molecule schema query it for new tasks to submit and either add them to qcarchive or put them in the
        local task queue.
        """
        datasets = optimization.build_qcsubmit_datasets()
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
        record_map: Dict[str, Dict[str, List[str]]],
        client: FractalClient,
    ) -> List[QCResultCollection]:
        """
        For the given list of record ids per dataset type collect all of the results.
        """
        dataset_types = {
            "hessian": BasicResultCollection,
            "optimization": OptimizationResultCollection,
            "torsion1d": TorsionDriveResultCollection,
        }

        result_collections = []

        for dataset_type, records in record_map.items():

            if len(records) == 0:
                continue

            result_type = dataset_types[dataset_type.lower()]

            for spec_name, entries in records.items():

                results = result_type.from_server(
                    client=client,
                    datasets=[self._dataset_name],
                    spec_name=spec_name,
                )

                result_collections.append(results)

        return result_collections

    def restart_archive_record(
        self,
        task: Union[ResultRecord, OptimizationRecord, TorsionDriveRecord],
        client: FractalClient,
    ):
        """
        Take a record and dispatch the type of restart to be done.
        """
        if task.__class__ == ResultRecord:
            logger.debug("Restarting basic task")
            self.restart_basic(
                [
                    task.id,
                ],
                client=client,
            )
        elif task.__class__ == OptimizationRecord:
            logger.debug("Restarting optimization")
            self.restart_optimizations(
                [
                    task.id,
                ],
                client=client,
            )
        else:
            logger.debug("Restarting torsiondrives and optimizations ...")
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
        self, torsiondrive_ids: List[ObjectId], client: FractalClient
    ) -> None:
        """
        Restart all torsiondrive records.
        """
        for td in torsiondrive_ids:
            client.modify_services("restart", procedure_id=td)

    def restart_optimizations(
        self, optimization_ids: List[ObjectId], client: FractalClient
    ) -> None:
        """
        Restart all optimizations.
        """
        for opt in optimization_ids:
            client.modify_tasks(operation="restart", base_result=opt)

    def restart_basic(self, basic_ids: List[ObjectId], client: [FractalClient]) -> None:
        """
        Restart all basic single point tasks.
        """
        pass

    def optimizer(self):
        """
        Monitors the optimizer queue and runs any tasks that arrive in the list.
        """

        sent_tasks = 0
        while True:
            task: BespokeOptimizationSchema = self.opt_queue.get()
            logger.info(f"Found Bespokefit task with id {task.id}")

            # make sure it is ready for fitting
            if task.ready_for_fitting:
                # now we need to set up the optimizer
                logger.debug(f"Sending task for optimization {task.id}")
                optimizer_class = get_optimizer(optimizer_name=task.optimizer.type)
                result = optimizer_class.optimize(
                    schema=task, keep_files=self.keep_files
                )
                if result.status == Status.ConvergenceError:
                    logger.warning(
                        f"The optimization {result.input_schema.id} failed to converge "
                        f"the best results were still collected.",
                    )
                # check for running QM tasks
                if task.get_task_map():
                    logger.debug("QCFractal task found putting back into queue")
                    # submit to the collection queue again
                    self.collection_queue.put(task)
                else:
                    # the task is finished so send it back
                    logger.info(f"Task complete with id {task.id}")
                    self.finished_tasks.put(result)
                    sent_tasks += 1
            else:
                # the task has an error so fail it
                self.finished_tasks.put(result)
                sent_tasks += 1

            # kill condition
            if sent_tasks == self.total_tasks:
                logger.warning("Killing all workers")
                self.collection_queue.put("END")
                break
