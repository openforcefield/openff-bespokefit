from typing import Optional, Union

from pydantic import BaseModel, Field
from qcelemental.models import AtomicResult, FailedOperation, OptimizationResult
from qcengine.procedures.torsiondrive import TorsionDriveResult
from typing_extensions import Literal

from openff.bespokefit.executor.utilities.typing import Status
from openff.bespokefit.schema.tasks import HessianTask, OptimizationTask, Torsion1DTask


class QCGeneratorBaseResponse(BaseModel):

    qc_calc_id: str = Field(
        ..., description="The ID associated with the QC calculation."
    )
    qc_calc_type: Literal["torsion1d", "optimization", "hessian"] = Field(
        ..., description="The type of QC calculation being run."
    )


class QCGeneratorGETStatusResponse(BaseModel):

    qc_calc_status: Status = Field(
        "waiting", description="The status of the QC calculation."
    )


class QCGeneratorGETResultResponse(BaseModel):

    qc_calc_result: Optional[
        Union[AtomicResult, OptimizationResult, TorsionDriveResult, FailedOperation]
    ] = Field(..., description="The result of the QC calculation if any was produced.")


class QCGeneratorGETErrorResponse(BaseModel):

    qc_calc_error: Optional[str] = Field(
        ..., description="The error raised while running the QC calculation if any."
    )


class QCGeneratorGETResponse(
    QCGeneratorBaseResponse,
    QCGeneratorGETStatusResponse,
    QCGeneratorGETResultResponse,
    QCGeneratorGETErrorResponse,
):
    """The object model returned by a GET request."""


class QCGeneratorPOSTBody(BaseModel):

    input_schema: Union[HessianTask, OptimizationTask, Torsion1DTask] = Field(
        ..., description="The schema that fully defines the QC data to generate."
    )


class QCGeneratorPOSTResponse(QCGeneratorBaseResponse):
    """The object model returned by a POST request."""
