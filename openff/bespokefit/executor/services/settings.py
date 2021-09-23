from pydantic import BaseSettings


class Settings(BaseSettings):

    BEFLOW_API_V1_STR: str = "/api/v1"

    BEFLOW_GATEWAY_PORT: int = 8000
    BEFLOW_GATEWAY_LOG_LEVEL: str = "error"

    BEFLOW_REDIS_ADDRESS: str = "localhost"
    BEFLOW_REDIS_PORT: int = 6379
    BEFLOW_REDIS_DB: int = 0

    BEFLOW_COORDINATOR_PREFIX = "optimization"
    BEFLOW_COORDINATOR_ROUTER = (
        "openff.bespokefit.executor.services.coordinator.app:router"
    )
    BEFLOW_COORDINATOR_WORKER = (
        "openff.bespokefit.executor.services.coordinator.worker:"
    )

    BEFLOW_FRAGMENTER_PREFIX = "fragmenter"
    BEFLOW_FRAGMENTER_ROUTER = (
        "openff.bespokefit.executor.services.fragmenter.app:router"
    )
    BEFLOW_FRAGMENTER_WORKER = "openff.bespokefit.executor.services.fragmenter.worker"

    BEFLOW_QC_COMPUTE_PREFIX = "qc-calc"
    BEFLOW_QC_COMPUTE_ROUTER = (
        "openff.bespokefit.executor.services.qcgenerator.app:router"
    )
    BEFLOW_QC_COMPUTE_WORKER = "openff.bespokefit.executor.services.qcgenerator.worker"

    BEFLOW_OPTIMIZER_PREFIX = "optimizer"
    BEFLOW_OPTIMIZER_ROUTER = "openff.bespokefit.executor.services.optimizer.app:router"
    BEFLOW_OPTIMIZER_WORKER = "openff.bespokefit.executor.services.optimizer.worker"
