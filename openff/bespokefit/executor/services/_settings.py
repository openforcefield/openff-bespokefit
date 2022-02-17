import os
from contextlib import contextmanager
from typing import Optional, Union

from pydantic import BaseSettings, Field
from typing_extensions import Literal

from openff.bespokefit.utilities.pydantic import BaseModel


class WorkerSettings(BaseModel):

    import_path: str = Field(..., description="The import path to the worker module.")

    n_cores: Optional[int] = Field(
        ..., description="The maximum number of cores available to the worker."
    )
    max_memory: Optional[float] = Field(
        ..., description="The maximum memory [GB] available to the worker *per* core."
    )


class Settings(BaseSettings):

    BEFLOW_API_V1_STR: str = "/api/v1"

    BEFLOW_GATEWAY_PORT: int = 8000
    BEFLOW_GATEWAY_LOG_LEVEL: str = "error"

    BEFLOW_REDIS_ADDRESS: str = "localhost"
    BEFLOW_REDIS_PORT: int = 6379
    BEFLOW_REDIS_DB: int = 0

    BEFLOW_COORDINATOR_PREFIX = "tasks"
    BEFLOW_COORDINATOR_ROUTER = (
        "openff.bespokefit.executor.services.coordinator.app:router"
    )
    BEFLOW_COORDINATOR_WORKER = (
        "openff.bespokefit.executor.services.coordinator.worker:"
    )

    BEFLOW_FRAGMENTER_PREFIX = "fragmentations"
    BEFLOW_FRAGMENTER_ROUTER = (
        "openff.bespokefit.executor.services.fragmenter.app:router"
    )
    BEFLOW_FRAGMENTER_WORKER = "openff.bespokefit.executor.services.fragmenter.worker"
    BEFLOW_FRAGMENTER_WORKER_N_CORES: Union[int, Literal["auto"]] = "auto"
    BEFLOW_FRAGMENTER_WORKER_MAX_MEM: Union[float, Literal["auto"]] = "auto"

    BEFLOW_QC_COMPUTE_PREFIX = "qc-calcs"
    BEFLOW_QC_COMPUTE_ROUTER = (
        "openff.bespokefit.executor.services.qcgenerator.app:router"
    )
    BEFLOW_QC_COMPUTE_WORKER = "openff.bespokefit.executor.services.qcgenerator.worker"
    BEFLOW_QC_COMPUTE_WORKER_N_CORES: Union[int, Literal["auto"]] = "auto"
    BEFLOW_QC_COMPUTE_WORKER_MAX_MEM: Union[float, Literal["auto"]] = "auto"

    BEFLOW_OPTIMIZER_PREFIX = "optimizations"
    BEFLOW_OPTIMIZER_ROUTER = "openff.bespokefit.executor.services.optimizer.app:router"
    BEFLOW_OPTIMIZER_WORKER = "openff.bespokefit.executor.services.optimizer.worker"
    BEFLOW_OPTIMIZER_WORKER_N_CORES: Union[int, Literal["auto"]] = "auto"
    BEFLOW_OPTIMIZER_WORKER_MAX_MEM: Union[float, Literal["auto"]] = "auto"
    BEFLOW_OPTIMIZER_KEEP_FILES: bool = False

    @property
    def fragmenter_settings(self) -> WorkerSettings:

        return WorkerSettings(
            import_path=self.BEFLOW_FRAGMENTER_WORKER,
            n_cores=None
            if self.BEFLOW_FRAGMENTER_WORKER_N_CORES == "auto"
            else self.BEFLOW_FRAGMENTER_WORKER_N_CORES,
            max_memory=None
            if self.BEFLOW_FRAGMENTER_WORKER_MAX_MEM == "auto"
            else self.BEFLOW_FRAGMENTER_WORKER_MAX_MEM,
        )

    @property
    def qc_compute_settings(self) -> WorkerSettings:

        return WorkerSettings(
            import_path=self.BEFLOW_QC_COMPUTE_WORKER,
            n_cores=None
            if self.BEFLOW_QC_COMPUTE_WORKER_N_CORES == "auto"
            else self.BEFLOW_QC_COMPUTE_WORKER_N_CORES,
            max_memory=None
            if self.BEFLOW_QC_COMPUTE_WORKER_MAX_MEM == "auto"
            else self.BEFLOW_QC_COMPUTE_WORKER_MAX_MEM,
        )

    @property
    def optimizer_settings(self) -> WorkerSettings:
        return WorkerSettings(
            import_path=self.BEFLOW_OPTIMIZER_WORKER,
            n_cores=None
            if self.BEFLOW_OPTIMIZER_WORKER_N_CORES == "auto"
            else self.BEFLOW_OPTIMIZER_WORKER_N_CORES,
            max_memory=None
            if self.BEFLOW_OPTIMIZER_WORKER_MAX_MEM == "auto"
            else self.BEFLOW_OPTIMIZER_WORKER_MAX_MEM,
        )

    @contextmanager
    def apply_env(self):
        """Applies a context manager that will temporarily update the global
        environmental variables to match the settings in this object.
        """

        variables_old = dict(os.environ)
        os.environ.update({key: str(value) for key, value in self.dict().items()})

        try:
            yield
        finally:
            os.environ.clear()
            os.environ.update(variables_old)
