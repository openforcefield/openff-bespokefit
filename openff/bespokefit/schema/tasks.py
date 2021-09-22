import abc
from typing import Literal, Tuple

from pydantic import BaseModel, Field, conint
from qcelemental.models.common_models import Model


class OptimizationSpec(BaseModel):

    procedure: Literal["geometric"] = "geometric"

    max_iterations: conint(gt=0) = Field(
        300,
        description="The maximum number of iterations to perform before raising a "
        "convergence failure exception.",
    )


class QCGenerationTask(BaseModel, abc.ABC):

    type: Literal["base-task"]


class HessianTaskSpec(QCGenerationTask):

    type: Literal["hessian"] = "hessian"

    n_conformers: conint(gt=0) = Field(
        10,
        description="The maximum number of conformers to generate when computing the "
        "hessian. Each conformer will be minimized and the one with the lowest energy "
        "will have its hessian computed.",
    )

    program: str = Field(..., description="The program to use to evaluate the model.")
    model: Model = Field(..., description=str(Model.__doc__))

    optimization_spec: OptimizationSpec = Field(
        OptimizationSpec(),
        description="The specification for how to optimize each conformer before "
        "computing the hessian.",
    )


class HessianTask(HessianTaskSpec):

    smiles: str = Field(
        ...,
        description="A fully indexed SMILES representation of the molecule to compute "
        "the hessian for.",
    )


class OptimizationTaskSpec(QCGenerationTask):
    type: Literal["optimization"] = "optimization"

    n_conformers: conint(gt=0) = Field(
        ...,
        description="The maximum number of conformers to begin the optimization from.",
    )

    program: str = Field(..., description="The program to use to evaluate the model.")
    model: Model = Field(..., description=str(Model.__doc__))

    optimization_spec: OptimizationSpec = Field(
        OptimizationSpec(),
        description="The specification for how to optimize each conformer.",
    )


class OptimizationTask(OptimizationTaskSpec):

    smiles: str = Field(
        ...,
        description="A fully indexed SMILES representation of the molecule to optimize.",
    )


class Torsion1DTaskSpec(QCGenerationTask):

    type: Literal["torsion1d"] = "torsion1d"

    grid_spacing: int = Field(15, description="The spacing between grid angles.")
    scan_range: Tuple[int, int] = Field(
        (-180, 165), description="The range of grid angles to scan."
    )

    program: str = Field(..., description="The program to use to evaluate the model.")
    model: Model = Field(..., description=str(Model.__doc__))

    optimization_spec: OptimizationSpec = Field(
        OptimizationSpec(),
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
