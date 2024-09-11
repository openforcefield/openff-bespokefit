from typing import TYPE_CHECKING, List, Optional, Type, TypeVar, Union

import requests
from openff.toolkit.typing.engines.smirnoff import ForceField
from requests.adapters import HTTPAdapter, Retry

from openff.bespokefit._pydantic import BaseModel, Field
from openff.bespokefit.executor.services import Settings
from openff.bespokefit.executor.services.coordinator.models import (
    CoordinatorGETPageResponse,
    CoordinatorGETResponse,
    CoordinatorGETStageStatus,
    CoordinatorPOSTBody,
    CoordinatorPOSTResponse,
)
from openff.bespokefit.executor.utilities.typing import Status
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults

if TYPE_CHECKING:
    import rich

_T = TypeVar("_T")


class BespokeExecutorStageOutput(BaseModel):
    """A model that stores the output of a particular stage in the bespoke fitting
    workflow e.g. QC data generation."""

    type: str = Field(..., description="The type of stage.")

    status: Status = Field(..., description="The status of the stage.")

    error: Optional[str] = Field(
        ..., description="The error, if any, raised by the stage."
    )


class BespokeExecutorOutput(BaseModel):
    """A model that stores the current output of running bespoke fitting workflow
    including any partial or final results."""

    smiles: str = Field(
        ...,
        description="The SMILES representation of the molecule that the bespoke "
        "parameters are being generated for.",
    )

    stages: List[BespokeExecutorStageOutput] = Field(
        ..., description="The outputs from each stage in the bespoke fitting process."
    )
    results: Optional[BespokeOptimizationResults] = Field(
        None,
        description="The final result of the bespoke optimization if the full workflow "
        "is finished, or ``None`` otherwise.",
    )

    @property
    def bespoke_force_field(self) -> Optional[ForceField]:
        """The final bespoke force field if the bespoke fitting workflow is complete."""

        if self.results is None or self.results.refit_force_field is None:
            return None

        return ForceField(
            self.results.refit_force_field, allow_cosmetic_attributes=True
        )

    @property
    def status(self) -> Status:
        pending_stages = [stage for stage in self.stages if stage.status == "waiting"]

        running_stages = [stage for stage in self.stages if stage.status == "running"]
        assert len(running_stages) < 2

        running_stage = None if len(running_stages) == 0 else running_stages[0]

        complete_stages = [
            stage
            for stage in self.stages
            if stage not in pending_stages and stage not in running_stages
        ]

        if (
            running_stage is None
            and len(complete_stages) == 0
            and len(pending_stages) > 0
        ):
            return "waiting"

        if any(stage.status == "errored" for stage in complete_stages):
            return "errored"

        if running_stage is not None or len(pending_stages) > 0:
            return "running"

        if all(stage.status == "success" for stage in complete_stages):
            return "success"

        raise NotImplementedError()

    @property
    def error(self) -> Optional[str]:
        """The error that caused the fitting to fail if any"""

        if self.status != "errored":
            return None

        message = next(
            iter(stage.error for stage in self.stages if stage.status == "errored")
        )
        return "unknown error" if message is None else message

    @classmethod
    def from_response(cls: Type[_T], response: CoordinatorGETResponse) -> _T:
        """Creates an instance of this object from the response from a bespoke
        coordinator service."""

        return cls(
            smiles=response.smiles,
            stages=[
                BespokeExecutorStageOutput(
                    type=stage.type, status=stage.status, error=stage.error
                )
                for stage in response.stages
            ],
            results=response.results,
        )


class BespokeFitClient:
    """
    A client interface which can be used to connect to a BespokeFit executor instance to submit and retrieve results.
    """

    def __init__(
        self,
        settings: Settings,
        retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        # If we are using a token with https warn the user
        if settings.BEFLOW_API_TOKEN and "https" not in settings.BEFLOW_GATEWAY_ADDRESS:
            import warnings

            warnings.warn(
                "Using an API token without an https connection is insecure, consider using https for encrypted comunication."
            )
        self._session = requests.Session()
        self._session.headers.update({"bespokefit-token": settings.BEFLOW_API_TOKEN})
        retry = Retry(connect=retries, backoff_factor=backoff_factor)
        adapter = HTTPAdapter(max_retries=retry)
        # replace the defaults with a retry version
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        self.address = (
            f"{settings.BEFLOW_GATEWAY_ADDRESS}:{settings.BEFLOW_GATEWAY_PORT}"
        )
        self.executor_url = f"{self.address}{settings.BEFLOW_API_V1_STR}/"
        self.coordinator_url = (
            f"{self.executor_url}{settings.BEFLOW_COORDINATOR_PREFIX}"
        )
        self.fragmenter_url = f"{self.executor_url}{settings.BEFLOW_FRAGMENTER_PREFIX}"
        self.qc_compute_url = f"{self.executor_url}{settings.BEFLOW_QC_COMPUTE_PREFIX}"
        self.optimizer_url = f"{self.executor_url}{settings.BEFLOW_OPTIMIZER_PREFIX}"

    def submit_optimization(self, input_schema: BespokeOptimizationSchema) -> str:
        """Submits a new bespoke fitting workflow to the executor.

        Args:
            input_schema: The schema defining the optimization to perform.

        Returns:
            The unique ID assigned to the optimization to perform.
        """
        request = self._session.post(
            self.coordinator_url,
            data=CoordinatorPOSTBody(input_schema=input_schema).json(),
        )
        request.raise_for_status()

        return CoordinatorPOSTResponse.parse_raw(request.text).id

    def _query_coordinator(self, optimization_href: str) -> CoordinatorGETResponse:
        coordinator_request = self._session.get(optimization_href)
        coordinator_request.raise_for_status()

        return CoordinatorGETResponse.parse_raw(coordinator_request.text)

    def get_optimization(self, optimization_id: str) -> BespokeExecutorOutput:
        """Retrieve the current state of a running bespoke fitting workflow.

        Args:
            optimization_id: The unique ID associated with the running optimization.

        Returns:
            The BespokeExecutorOutput which contains information about the optimization and links the relevant
            stages as well as the final parameters if the optimization if finished.
        """

        optimization_href = f"{self.coordinator_url}/{optimization_id}"
        return BespokeExecutorOutput.from_response(
            self._query_coordinator(optimization_href=optimization_href)
        )

    def list_optimizations(
        self, status: Optional[Status] = None
    ) -> CoordinatorGETPageResponse:
        """
        Get a list the first 1000 running calculations with the requested status.

        Args:
            status: The status we want to check.

        Returns:
            A CoordinatorGETPageResponse linking to the relevant optimization ids which can then be sorted.
        """
        # In the coordinator we keep both successful and errored tasks in the same 'complete'
        # queue to avoid having to maintain and query to separate lists in redis, so here we
        # need to condense these two states into one and then apply a second filter when
        # iterating over the returned ids.
        status_url = (
            None
            if status is None
            else status.replace("success", "complete").replace("errored", "complete")
        )
        status_url = "" if status_url is None else f"?status={status_url}"
        request = self._session.get(f"{self.coordinator_url}{status_url}")
        request.raise_for_status()

        return CoordinatorGETPageResponse.parse_raw(request.content)

    def wait_until_complete(
        self,
        optimization_id: str,
        console: Optional["rich.Console"] = None,
        frequency: Union[int, float] = 5,
    ) -> BespokeExecutorOutput:
        """Wait for a specified optimization to complete and return the results.

        Args:
            optimization_id: The unique id of the optimization to wait for.
            console: The console to print to.
            frequency: The frequency (seconds) with which to poll the status of the
                optimization.

        Returns:
            The output of running the optimization.
        """
        import rich
        from rich.padding import Padding

        console = console if console is not None else rich.get_console()

        optimization_response = self.get_optimization(optimization_id=optimization_id)
        stage_types = [stage.type for stage in optimization_response.stages]

        stage_messages = {
            "fragmentation": "fragmenting the molecule",
            "qc-generation": "generating bespoke QC data",
            "optimization": "optimizing the parameters",
        }

        for stage_type in stage_messages:
            if stage_type not in stage_types:
                continue

            with console.status(stage_messages[stage_type]):
                stage = self._wait_for_stage(
                    optimization_id=optimization_id,
                    stage_type=stage_type,
                    frequency=frequency,
                )

            if stage.status == "errored":
                console.print(f"[[red]x[/red]] {stage_type} failed")
                console.print(Padding(stage.error, (1, 0, 0, 1)))

                break

            console.print(f"[[green]✓[/green]] {stage_type} successful")

        return self.get_optimization(optimization_id=optimization_id)

    def _wait_for_stage(
        self, optimization_id: str, stage_type: str, frequency: Union[int, float] = 5
    ) -> CoordinatorGETStageStatus:
        import time

        while True:
            query = f"{self.coordinator_url}/{optimization_id}"
            response = self._query_coordinator(optimization_href=query)

            stage = {stage.type: stage for stage in response.stages}[stage_type]

            if stage.status in ["errored", "success"]:
                break

            time.sleep(frequency)

        return stage
