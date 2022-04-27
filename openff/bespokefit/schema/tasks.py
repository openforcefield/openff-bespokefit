import abc
from typing import Optional, Tuple, overload

from openff.qcsubmit.procedures import GeometricProcedure
from openff.toolkit.topology import Molecule
from pydantic import Field, conint
from qcelemental.models import AtomicResult
from qcelemental.models.common_models import Model
from qcelemental.models.procedures import OptimizationResult, TorsionDriveResult
from typing_extensions import Literal

from openff.bespokefit.utilities.pydantic import BaseModel


class QCGenerationTask(BaseModel, abc.ABC):

    type: Literal["base-task"] = "base-task"

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

    optimization_spec: GeometricProcedure = Field(
        GeometricProcedure(enforce=0.1, reset=True, qccnv=True, epsilon=0.0),
        description="The specification for how to optimize the structure at each angle "
        "in the scan.",
    )

    n_conformers: conint(gt=0) = Field(
        10,
        description="The number of initial conformers to seed the torsion drive with.",
    )
    sp_specification: Optional[QCGenerationTask] = Field(
        None,
        description="An extra optional specification used to compute the reference energy surface on the optimised geometries.",
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


@overload
def task_from_result(result: AtomicResult) -> HessianTask:
    ...


@overload
def task_from_result(result: OptimizationResult) -> OptimizationTask:
    ...


@overload
def task_from_result(result: TorsionDriveResult) -> Torsion1DTask:
    ...


def task_from_result(result):
    """
    Convert a result into a task to populate the cache for the result.
    """

    if isinstance(result, TorsionDriveResult):
        dihedral = result.keywords.dihedrals[0]
        off_mol = Molecule.from_qcschema(result.initial_molecule[0])
        return Torsion1DTask(
            smiles=off_mol.to_smiles(
                isomeric=True, explicit_hydrogens=True, mapped=True
            ),
            program=result.extras["program"],
            model=result.input_specification.model,
            central_bond=(dihedral[1] + 1, dihedral[2] + 1),
            grid_spacing=result.keywords.grid_spacing[0],
            scan_range=result.keywords.dihedral_ranges,
            optimization_spec=GeometricProcedure.from_opt_spec(
                result.optimization_spec
            ),
        )
    else:
        raise NotImplementedError()
