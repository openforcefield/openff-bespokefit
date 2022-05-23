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


class SinglePointSpec(BaseModel):
    """Defines the specification for performing a single point calculation."""

    program: str = Field(description="The program to use to evaluate the model.")
    model: Model = Field(description="The QC model to perform the single point using.")


class OptimizationSpec(SinglePointSpec):
    """Defines the specification for performing a conformer optimization."""

    procedure: GeometricProcedure = Field(
        GeometricProcedure(),
        description="The procedure to follow when optimizing the conformer.",
    )


class BaseTaskSpec(BaseModel, abc.ABC):
    """The base for tasks that will generate QC reference data that force field
    parameters will be trained to.
    """

    type: Literal["base-task"]


class HessianTaskSpec(BaseTaskSpec):
    """

    Examples:

        Define the specification for a task that will optimize an initial set of *up to*
        10 diverse conformers at the B3LYP-D3BJ/DZVP level of theory before finally
        evaluting the hessian of the conformer with the lowest energy:

        >>> HessianTaskSpec(
        >>>     optimization_spec=OptimizationSpec(
        >>>         model=Model(method="B3LYP-D3BJ", basis="DZVP"), program="psi4",
        >>>     )
        >>>     n_conformers=10,
        >>> )

        Create a specification for a task that will pre-optimize a set of conformers
        using GFN2XTB, followed by a second optimization using B3LYP-D3BJ/DZVP, before
        finally evaluting the hessian of the conformer with the lowest energy using
        B3LYP-D3BJ/DZVP:

        >>> HessianTaskSpec(
        >>>     pre_optimization_spec=OptimizationSpec(
        >>>         model=Model(method="GFN2XTB", basis=None), program="xtb",
        >>>     ),
        >>>     optimization_spec=OptimizationSpec(
        >>>         model=Model(method="B3LYP-D3BJ", basis="DZVP"), program="psi4",
        >>>     )
        >>> )
    """

    type: Literal["hessian"] = "hessian"

    n_conformers: conint(gt=0) = Field(
        10,
        description="The maximum number of conformers to generate when computing the "
        "hessian. Each conformer will be minimized and the one with the lowest energy "
        "will have its hessian computed.",
    )

    pre_optimization_spec: Optional[OptimizationSpec] = Field(
        None,
        description="The (optional) specification to follow when pre-optimizing each "
        "conformer using a 'cheaper' level of theory. If no value is provided, a "
        "pre-optimization will not be performed.",
    )
    optimization_spec: OptimizationSpec = Field(
        description="The specification for how to optimize each conformer before "
        "computing the hessian of the lowest energy conformer.",
    )


class HessianTask(HessianTaskSpec):

    smiles: str = Field(
        description="A fully indexed SMILES representation of the molecule to compute "
        "the hessian for.",
    )


class OptimizationTaskSpec(HessianTaskSpec):
    """
    Examples:

        Optimize multiple conformers of a molecule at the B3LYP-D3BJ/DZVP level of
        theory

        >>> OptimizationTaskSpec(
        >>>     optimization_spec=OptimizationSpec(
        >>>         model=Model(method="B3LYP-D3BJ", basis="DZVP"), program="psi4",
        >>>     )
        >>> )

        Optimize multiple conformers of a molecule first using GFN2XTB, followed by
        a second optimization using B3LYP-D3BJ/DZVP:

        >>> OptimizationTaskSpec(
        >>>     pre_optimization_spec=OptimizationSpec(
        >>>         model=Model(method="GFN2XTB", basis=None), program="xtb",
        >>>     ),
        >>>     optimization_spec=OptimizationSpec(
        >>>         model=Model(method="B3LYP-D3BJ", basis="DZVP"), program="psi4",
        >>>     )
        >>> )

        Optimize multiple conformers of a molecule using GFN2XTB before evaluating
        the final energy of each conformer using B3LYP-D3BJ/DZVP:

        >>> OptimizationTaskSpec(
        >>>     optimization_spec=OptimizationSpec(
        >>>         model=Model(method="GFN2XTB", basis=None), program="xtb",
        >>>     ),
        >>>     evaluation_spec=SinglePointSpec(
        >>>         model=Model(method="B3LYP-D3BJ", basis="DZVP"), program="psi4",
        >>>     )
        >>> )
    """

    type: Literal["optimization"] = "optimization"

    # Redefine base field to give a more specific description.
    optimization_spec: OptimizationSpec = Field(
        description="The specification for how to optimize each conformer.",
    )
    evaluation_spec: Optional[SinglePointSpec] = Field(
        None,
        description="The (optional) specification to follow when evaluating properties "
        "of the final conformer such as the energy and gradient.",
    )


class OptimizationTask(OptimizationTaskSpec):

    smiles: str = Field(
        description="A fully indexed SMILES representation of the molecule to optimize.",
    )


class Torsion1DTaskSpec(BaseTaskSpec):

    type: Literal["torsion1d"] = "torsion1d"

    grid_spacing: int = Field(15, description="The spacing between grid angles.")
    scan_range: Optional[Tuple[int, int]] = Field(
        None, description="The range of grid angles to scan."
    )

    optimization_spec: OptimizationSpec = Field(
        description="The specification for how to optimize each conformer at each "
        "grid angle.",
    )
    evaluation_spec: Optional[SinglePointSpec] = Field(
        None,
        description="The (optional) specification to follow when evaluating evaluating "
        "the energy at each grid angle. If no value is provided the level of theory "
        "used to optimize the conformer at each grid angle will be used.",
    )

    n_conformers: conint(gt=0) = Field(
        10,
        description="The number of initial conformers to seed the torsion drive with.",
    )


class Torsion1DTask(Torsion1DTaskSpec):

    smiles: str = Field(
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
            central_bond=(dihedral[1] + 1, dihedral[2] + 1),
            grid_spacing=result.keywords.grid_spacing[0],
            scan_range=result.keywords.dihedral_ranges,
            optimization_spec=OptimizationSpec(
                program=result.extras["program"],
                model=result.input_specification.model,
                procedure=GeometricProcedure.from_opt_spec(result.optimization_spec),
            ),
        )
    else:
        raise NotImplementedError()
