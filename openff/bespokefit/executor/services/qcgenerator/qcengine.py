from collections import defaultdict
from multiprocessing import Pool
from typing import Dict, List, Union

from qcelemental.models import FailedOperation
from qcelemental.models.procedures import OptimizationResult, TorsionDriveInput
from qcengine.config import TaskConfig
from qcengine.procedures import register_procedure
from qcengine.procedures.torsiondrive import TorsionDriveProcedure

from openff.bespokefit.executor.services import current_settings


def _divide_config(config: TaskConfig, n_workers: int) -> TaskConfig:
    """
    Divide the total resource for the worker between the parallel optimizations.
    """
    return TaskConfig(
        ncores=int(config.ncores / n_workers),
        memory=int(config.memory / n_workers),
        retries=2,
        nnodes=1,
    )


class TorsionDriveProcedureParallel(TorsionDriveProcedure):
    """
    Override the _spawn_optimizations method of the basic torsiondrive procedure to allow for parallel optimizations
    within one worker.
    """

    _defaults = {"name": "TorsionDriveParallel", "procedure": "torsiondrive"}

    def _spawn_optimizations(
        self,
        next_jobs: Dict[str, List[float]],
        input_model: TorsionDriveInput,
        config: TaskConfig,
    ) -> Dict[str, List[Union[FailedOperation, OptimizationResult]]]:
        """
        Spawn parallel optimizations based on the number of next jobs and available workers.
        """

        _settings = current_settings()
        opts_per_worker = _settings.BEFLOW_QC_COMPUTE_WORKER_N_TASKS
        final_results = defaultdict(list)
        n_jobs = sum([len(value) for value in next_jobs.values()])
        if opts_per_worker > 1 and n_jobs > 1:
            # split the resources based on the number of tasks
            n_workers = int(min([n_jobs, opts_per_worker]))
            opt_config = _divide_config(config=config, n_workers=n_workers)
            work_list = []
            with Pool(processes=n_workers) as pool:
                for grid_point, jobs in next_jobs.items():
                    for job in jobs:
                        task = pool.apply_async(
                            func=self._spawn_optimization,
                            args=(grid_point, job, input_model, opt_config),
                        )
                        work_list.append(task)
                        final_results[grid_point].append(task._job)

                # now loop over the work and pull results and replace values
                for work in work_list:
                    result = work.get()
                    for jobs in final_results.values():
                        if work._job in jobs:
                            index = jobs.index(work._job)
                            jobs[index] = result

            return final_results
        else:
            return {
                grid_point: [
                    self._spawn_optimization(grid_point, job, input_model, config)
                    for job in jobs
                ]
                for grid_point, jobs in next_jobs.items()
            }


# register for local usage
register_procedure(TorsionDriveProcedureParallel())
