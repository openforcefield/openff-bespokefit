from typing import List, Optional

from pydantic import BaseModel, Field

from openff.bespokefit.executor.services.coordinator.stages import StageType
from openff.bespokefit.executor.utilities.typing import Status
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults


class CoordinatorGETStageStatus(BaseModel):

    stage_type: str = Field(..., description="")

    stage_status: Status = Field(..., description="")
    stage_error: Optional[str] = Field(..., description="")

    stage_ids: Optional[List[str]] = Field(..., description="")

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

        return CoordinatorGETStageStatus(
            stage_type=stage.type,
            stage_status=stage.status,
            stage_error=stage.error,
            stage_ids=stage_ids,
        )


class CoordinatorGETResponse(BaseModel):

    optimization_id: str = Field(
        ..., description="The ID associated with the bespoke optimization."
    )

    smiles: str = Field(..., description="")

    stages: List[CoordinatorGETStageStatus] = Field(..., description="")

    results: Optional[BespokeOptimizationResults] = Field(None, description="")

    @classmethod
    def from_task(cls, task: "CoordinatorTask"):

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
            optimization_id=task.id,
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


class CoordinatorPOSTResponse(BaseModel):

    optimization_id: str = Field(
        ..., description="The ID associated with the optimization."
    )


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

        return "success"
