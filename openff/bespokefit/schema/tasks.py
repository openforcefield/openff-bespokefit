import abc
from typing import Optional, Tuple

from openff.qcsubmit.procedures import GeometricProcedure
from pydantic import Field, conint
from qcelemental.models.common_models import Model
from typing_extensions import Literal

from openff.bespokefit.utilities.pydantic import BaseModel


class QCGenerationTask(BaseModel, abc.ABC):

    type: Literal["base-task"]

    program: str = Field(..., description="The program to use to evaluate the model.")
    model: Model = Field(..., description=str(Model.__doc__))


class HessianTaskSpec(QCGenerationTask):

    type: Literal["hessian"] = "hessian"

    n_conformers: conint(gt=0) = Field(
        10,
        description="The maximum number of conformers to generate when computing the "
        "hessian. Each conformer will be minimized and the one with the lowest energy "
        "will have its hessian computed.",
    )
    optimization_spec: GeometricProcedure = Field(
        GeometricProcedure(),
        description="The specification for how to optimize each conformer before "
        "computing the hessian.",
    )


class HessianTask(HessianTaskSpec):

    smiles: str = Field(
        ...,
        description="A fully indexed SMILES representation of the molecule to compute "
        "the hessian for.",
    )


class OptimizationTaskSpec(HessianTaskSpec):
    type: Literal["optimization"] = "optimization"


class OptimizationTask(OptimizationTaskSpec):

    smiles: str = Field(
        ...,
        description="A fully indexed SMILES representation of the molecule to optimize.",
    )


class Torsion1DTaskSpec(QCGenerationTask):

    type: Literal["torsion1d"] = "torsion1d"

    grid_spacing: int = Field(15, description="The spacing between grid angles.")
    scan_range: Optional[Tuple[int, int]] = Field(
        None, description="The range of grid angles to scan."
    )
    # update to use the default torsiondrive settings
    optimization_spec: GeometricProcedure = Field(
        GeometricProcedure(enforce=0.1, reset=True, qccnv=True, epsilon=0.0),
        description="The specification for how to optimize the structure at each angle "
        "in the scan.",
    )


class Torsion1DTask(Torsion1DTaskSpec):

    smiles: str = Field(
        ...,
        description="An indexed SMILES representation of the molecule to drive.",
    )
    central_bond: Tuple[int, int] = Field(
        None,
        description="The **map** indices of the atoms in the bond to scan around.",
    )
