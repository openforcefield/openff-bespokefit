"""Generate QC data using QCEngine."""
from multiprocessing import current_process, get_context
from typing import Union

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
        retries=config.retries,
        nnodes=1,
    )


class TorsionDriveProcedureParallel(TorsionDriveProcedure):
    """
    Override the _spawn_optimizations method of the basic torsiondrive procedure.

    Allows for parallel optimizations within one worker.

    """

    _defaults = {"name": "TorsionDriveParallel", "procedure": "torsiondrive"}

    def _spawn_optimizations(
        self,
        next_jobs: dict[str, list[list[float]]],
        input_model: TorsionDriveInput,
        config: TaskConfig,
    ) -> dict[str, list[Union[FailedOperation, OptimizationResult]]]:
        """Spawn parallel optimizations based on the number of next jobs and available workers."""
        settings = current_settings()
        program = input_model.optimization_spec.keywords["program"]
        opts_per_worker = settings.BEFLOW_QC_COMPUTE_WORKER_N_TASKS
        # we can only split the tasks if the celery worker is the main process so if not set back to 1
        if current_process().name != "MainProcess":
            opts_per_worker = 1

        if program == "psi4" and opts_per_worker == "auto":
            # we recommend 8 cores per worker for psi4 from our qcfractal jobs
            opts_per_worker = max([int(config.ncores / 8), 1])
        elif opts_per_worker == "auto":
            # for low cost methods like ani or xtb its often faster to not split the jobs
            opts_per_worker = 1

        n_jobs = sum([len(value) for value in next_jobs.values()])
        if opts_per_worker > 1 and n_jobs > 1:
            # split the resources based on the number of tasks
            n_workers = int(min([n_jobs, opts_per_worker]))
            opt_config = _divide_config(config=config, n_workers=n_workers)

            # Using fork can hang on our local HPC so pin to use spawn
            with get_context("spawn").Pool(processes=n_workers) as pool:
                tasks = {
                    grid_point: [
                        pool.apply_async(
                            func=self._spawn_optimization,
                            args=(grid_point, job, input_model, opt_config),
                        )
                        for job in jobs
                    ]
                    for grid_point, jobs in next_jobs.items()
                }
                return {
                    grid_point: [grid_task.get() for grid_task in grid_tasks]
                    for grid_point, grid_tasks in tasks.items()
                }

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
