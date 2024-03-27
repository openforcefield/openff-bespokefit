from typing import Optional

from openff.bespokefit._pydantic import BaseModel, Field
from openff.bespokefit.executor.services.models import Link
from openff.bespokefit.executor.utilities.typing import Status
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults


class OptimizerGETResponse(Link):
    """The object model returned by a GET request."""

    status: Status = Field("waiting", description="The status of the optimization.")

    result: Optional[BespokeOptimizationResults] = Field(
        ..., description="The result of the optimization if any was produced."
    )

    error: Optional[str] = Field(
        ..., description="The error raised while optimizing if any."
    )


class OptimizerPOSTBody(BaseModel):
    """The object model expected by a POST request."""

    input_schema: BespokeOptimizationSchema = Field(
        ..., description="The schema that fully defines optimization to perform."
    )


class OptimizerPOSTResponse(Link):
    """The object model returned by a POST request."""
