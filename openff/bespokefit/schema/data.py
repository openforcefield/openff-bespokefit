from typing import Generic, List, TypeVar

import numpy as np
from pydantic import Field
from pydantic.generics import GenericModel
from typing_extensions import Literal

from openff.bespokefit.schema.tasks import (
    HessianTaskSpec,
    OptimizationTaskSpec,
    Torsion1DTaskSpec,
)

QCDataType = TypeVar("QCDataType")
QCTaskSpec = TypeVar(
    "QCTaskSpec", HessianTaskSpec, OptimizationTaskSpec, Torsion1DTaskSpec
)


class BespokeQCData(GenericModel, Generic[QCTaskSpec]):

    type: Literal["bespoke"] = "bespoke"

    spec: QCTaskSpec = Field(
        ...,
        description="The specification that should be used to generate the reference "
        "data.",
    )


class LocalQCData(GenericModel, Generic[QCDataType]):
    class Config:
        json_encoders = {np.ndarray: lambda v: v.flatten().tolist()}

    type: Literal["local"] = "local"

    qc_records: List[QCDataType] = Field(..., description="A list of local QC results.")
