from typing import Optional

from pydantic import BaseModel, Field

from openff.bespokefit.executor.utilities.typing import Status
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults


class OptimizerBaseResponse(BaseModel):

    optimization_id: str = Field(
        ..., description="The ID associated with the optimization."
    )


class OptimizerGETStatusResponse(BaseModel):

    optimization_status: Status = Field(
        "waiting", description="The status of the optimization."
    )


class OptimizerGETResultResponse(BaseModel):

    optimization_result: Optional[BespokeOptimizationResults] = Field(
        ..., description="The result of the optimization if any was produced."
    )


class OptimizerGETErrorResponse(BaseModel):

    optimization_error: Optional[str] = Field(
        ..., description="The error raised while optimizing if any."
    )


class OptimizerGETResponse(
    OptimizerBaseResponse,
    OptimizerGETStatusResponse,
    OptimizerGETResultResponse,
    OptimizerGETErrorResponse,
):
    """The object model returned by a GET request."""


class OptimizerPOSTBody(BaseModel):
    """The object model expected by a POST request."""

    input_schema: BespokeOptimizationSchema = Field(
        ..., description="The schema that fully defines optimization to perform."
    )


class OptimizerPOSTResponse(OptimizerBaseResponse):
    """The object model returned by a POST request."""
