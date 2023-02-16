from typing import Dict, List, Optional

from pydantic import Field

from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.services.coordinator.stages import StageType
from openff.bespokefit.executor.services.models import Link, PaginatedCollection
from openff.bespokefit.executor.utilities.typing import Status
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults
from openff.bespokefit.utilities.pydantic import BaseModel


class CoordinatorGETPageResponse(PaginatedCollection[Link]):
    """"""


class CoordinatorGETStageStatus(BaseModel):
    type: str = Field(..., description="The type of stage.")

    status: Status = Field(..., description="The status of the stage.")
    error: Optional[str] = Field(
        ..., description="The error, if any, raised by the stage."
    )

    results: Optional[List[Link]] = Field(
        ..., description="Links to the results generated by this stage."
    )

    @classmethod
    def from_stage(cls, stage: StageType):
        stage_ids = stage.id if hasattr(stage, "id") else stage.ids

        if isinstance(stage_ids, str):
            stage_ids = [stage_ids]
        elif isinstance(stage_ids, dict):
            stage_ids = sorted(
                {
                    stage_id
                    for dict_values in stage_ids.values()
                    for stage_id in dict_values
                }
            )
        elif stage_ids is None:
            pass
        else:
            raise NotImplementedError()

        settings = current_settings()

        base_endpoint = f"{settings.BEFLOW_API_V1_STR}/"

        endpoints = {
            "fragmentation": f"{base_endpoint}{settings.BEFLOW_FRAGMENTER_PREFIX}/",
            "qc-generation": f"{base_endpoint}{settings.BEFLOW_QC_COMPUTE_PREFIX}/",
            "optimization": f"{base_endpoint}{settings.BEFLOW_OPTIMIZER_PREFIX}/",
        }

        return CoordinatorGETStageStatus(
            type=stage.type,
            status=stage.status,
            error=stage.error,
            results=None
            if stage_ids is None
            else [
                Link(id=stage_id, self=f"{endpoints[stage.type]}{stage_id}")
                for stage_id in stage_ids
            ],
        )


class CoordinatorGETResponse(Link):
    smiles: str = Field(
        ...,
        description="The SMILES representation of the molecule that the bespoke "
        "parameters are being generated for.",
    )

    stages: List[CoordinatorGETStageStatus] = Field(
        ..., description="The stages of the bespoke optimization."
    )
    results: Optional[BespokeOptimizationResults] = Field(
        None, description="The output of the bespoke optimization."
    )

    links: Dict[str, str] = Field(
        {}, description="Links to resources associated with the model.", alias="_links"
    )

    @classmethod
    def from_task(cls, task: "CoordinatorTask"):
        settings = current_settings()

        stages = [
            *task.pending_stages,
            *([] if task.running_stage is None else [task.running_stage]),
            *task.completed_stages,
        ]
        stages_by_type = {stage.type: stage for stage in stages}

        stage_responses = [
            CoordinatorGETStageStatus.from_stage(stage) for stage in stages
        ]

        return CoordinatorGETResponse(
            id=task.id,
            self=(
                f"{settings.BEFLOW_API_V1_STR}/"
                f"{settings.BEFLOW_COORDINATOR_PREFIX}/{task.id}"
            ),
            smiles=task.input_schema.smiles,
            stages=stage_responses,
            results=(
                None
                if "optimization" not in stages_by_type
                else stages_by_type["optimization"].result
            ),
        )


class CoordinatorPOSTBody(BaseModel):
    input_schema: BespokeOptimizationSchema = Field(..., description="")


class CoordinatorPOSTResponse(Link):
    """"""


class CoordinatorTask(BaseModel):
    """An internal model that tracks a task (i.e. a bespoke optimization) that is being
    executed by the executor.
    """

    id: str = Field(..., description="The unique ID associated with this task.")

    input_schema: BespokeOptimizationSchema = Field(..., description="")

    pending_stages: List[StageType] = Field(..., description="")

    running_stage: Optional[StageType] = Field(None, description="")

    completed_stages: List[StageType] = Field([], description="")

    @property
    def status(self) -> Status:
        if (
            self.running_stage is None
            and len(self.completed_stages) == 0
            and len(self.pending_stages) > 0
        ):
            return "waiting"

        if any(stage.status == "errored" for stage in self.completed_stages):
            return "errored"

        if self.running_stage is not None or len(self.pending_stages) > 0:
            return "running"

        if all(stage.status == "success" for stage in self.completed_stages):
            return "success"

        raise NotImplementedError()
