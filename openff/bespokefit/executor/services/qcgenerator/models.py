"""Models used in qc generation."""

from typing import Literal, Optional, Union

from pydantic import Field
from qcelemental.models import AtomicResult, FailedOperation, OptimizationResult
from qcengine.procedures.torsiondrive import TorsionDriveResult

from openff.bespokefit.executor.services.models import Link, PaginatedCollection
from openff.bespokefit.executor.utilities.typing import Status
from openff.bespokefit.schema.tasks import HessianTask, OptimizationTask, Torsion1DTask
from openff.bespokefit.utilities.pydantic import BaseModel


class QCGeneratorGETResponse(Link):
    """The object model returned by a GET request."""

    type: Literal["torsion1d", "optimization", "hessian"] = Field(
        ...,
        description="The type of QC calculation being run.",
    )

    status: Status = Field("waiting", description="The status of the QC calculation.")

    result: Optional[
        Union[AtomicResult, OptimizationResult, TorsionDriveResult, FailedOperation]
    ] = Field(..., description="The result of the QC calculation if any was produced.")

    error: Optional[str] = Field(
        ...,
        description="The error raised while running the QC calculation if any.",
    )

    links: dict[str, str] = Field(
        {},
        description="Links to resources associated with the model.",
        alias="_links",
    )


class QCGeneratorGETPageResponse(PaginatedCollection[QCGeneratorGETResponse]):
    """GET response of a QC generator."""


class QCGeneratorPOSTBody(BaseModel):
    """Body of POST for a QC generator."""

    input_schema: Union[HessianTask, OptimizationTask, Torsion1DTask] = Field(
        ...,
        description="The schema that fully defines the QC data to generate.",
    )


class QCGeneratorPOSTResponse(Link):
    """The object model returned by a POST request."""
