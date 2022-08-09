import abc
from typing import Any, Dict, Optional, Union, TypeVar

from openff.qcsubmit.results import (
    BasicResultCollection,
    OptimizationResultCollection,
    TorsionDriveResultCollection,
)
from openff.toolkit.topology import Molecule
from pydantic import Field, PositiveFloat, validator
from qcelemental.models import AtomicResult
from qcelemental.models.procedures import OptimizationResult, TorsionDriveResult
from qcelemental.molutil import guess_connectivity
from typing_extensions import Literal

from openff.bespokefit.schema.data import BespokeQCData, LocalQCData
from openff.bespokefit.schema.tasks import (
    HessianTaskSpec,
    OptimizationTaskSpec,
    Torsion1DTaskSpec,
)
from openff.bespokefit.utilities.pydantic import SchemaBase


R = TypeVar(
    "R",
    None,
    LocalQCData[TorsionDriveResult],
    LocalQCData[OptimizationResult],
    BespokeQCData[Torsion1DTaskSpec],
    BespokeQCData[OptimizationTaskSpec],
    OptimizationResultCollection,
    TorsionDriveResultCollection,
)


def _check_connectivity(
    cls,
    ref_data: R,
) -> R:
    """
    Check that connectivity has not changed over the course of QC computation.

    This function can be used as a validator for the ``reference_data`` field of
    a target schema if the connectivity may change over the course of computing
    the target:

        def __init__(...):
            ...
            _reference_data_connectivity = validator("reference_data", allow_reuse=True)(
                _check_connectivity
            )
            ...

    """
    if isinstance(ref_data, LocalQCData):
        for qc_record in ref_data.qc_records:
            # Some qc records (eg, TorsionDriveResult) use .final_molecules (plural),
            # others (eg, OptimizationResult) use .final_molecule (singular)
            try:
                final_molecules = qc_record.final_molecules
            except AttributeError:
                final_molecules = {"opt": qc_record.final_molecule}

            for name, qcschema in final_molecules.items():
                fragment = Molecule.from_qcschema(qcschema)

                # Get correct connectivity from the schema's SMILES
                expected_connectivity = {
                    tuple(sorted([bond.atom1_index + 1, bond.atom2_index + 1]))
                    for bond in fragment.bonds
                }

                # Get computed connectivity guessed from the output geometry
                actual_connectivity = {
                    tuple(sorted([a + 1, b + 1]))
                    for a, b in guess_connectivity(qcschema.symbols, qcschema.geometry)
                }

                if expected_connectivity != actual_connectivity:
                    # Pydantic validators must raise ValueError, TypeError or AssertionError
                    raise ValueError(
                        f"Target record {name}: "
                        + "Reference data does not match target.\n"
                        + f"Expected mapped SMILES: {fragment.to_smiles(mapped=True)}\n"
                        + "The following connections were expected but not found: "
                        + f"{expected_connectivity - actual_connectivity}\n"
                        + "The following connections were found but not expected: "
                        + f"{actual_connectivity - expected_connectivity}\n"
                    )
    # No connectivity changes found, so return the unchanged input as validated
    return ref_data


class BaseTargetSchema(SchemaBase, abc.ABC):
    """The base class for models which store information about fitting targets."""

    weight: PositiveFloat = Field(
        1.0, description="The amount to weight the target by."
    )

    reference_data: Optional[Union[Any, LocalQCData[Any], BespokeQCData[Any]]]

    calculation_specification: Optional[
        Union[Torsion1DTaskSpec, HessianTaskSpec, OptimizationTaskSpec]
    ]

    extras: Dict[str, str] = Field(
        {},
        description="Extra settings to use for the target. Optimizer specific settings "
        "(e.g. whether a target should be set to remote in ForceBalance) should be "
        "included here.",
    )

    @classmethod
    @abc.abstractmethod
    def bespoke_task_type(
        cls,
    ) -> Literal["torsion1d", "optimization", "hessian"]:
        """Returns the type of task which will be required to generate the reference
        data for this type of target.
        """
        raise NotImplementedError


class TorsionProfileTargetSchema(BaseTargetSchema):
    """A model which stores information about a torsion profile fitting target."""

    type: Literal["TorsionProfile"] = "TorsionProfile"

    reference_data: Optional[
        Union[
            LocalQCData[TorsionDriveResult],
            BespokeQCData[Torsion1DTaskSpec],
            TorsionDriveResultCollection,
        ]
    ] = Field(
        None,
        description="The reference QC data (either existing or to be generated on the "
        "fly) to fit against.",
    )
    _reference_data_connectivity = validator("reference_data", allow_reuse=True)(
        _check_connectivity
    )
    calculation_specification: Optional[Torsion1DTaskSpec] = Field(
        None,
        description="The specification for the reference torsion drive calculation, also acts as a provenance source.",
    )

    attenuate_weights: bool = Field(
        True, description="Whether to attenuate the weights as a function of energy."
    )

    energy_denominator: float = Field(
        1.0, description="The energy denominator in objective function contribution."
    )
    energy_cutoff: float = Field(10.0, description="The upper energy cutoff.")

    @classmethod
    def bespoke_task_type(cls) -> Literal["torsion1d"]:
        return "torsion1d"


class AbInitioTargetSchema(BaseTargetSchema):
    """A model which stores information about an ab initio fitting target."""

    type: Literal["AbInitio"] = "AbInitio"

    reference_data: Optional[
        Union[
            LocalQCData[TorsionDriveResult],
            BespokeQCData[Torsion1DTaskSpec],
            TorsionDriveResultCollection,
        ]
    ] = Field(
        None,
        description="The reference QC data (either existing or to be generated on the "
        "fly) to fit against.",
    )
    _reference_data_connectivity = validator("reference_data", allow_reuse=True)(
        _check_connectivity
    )
    calculation_specification: Optional[Torsion1DTaskSpec] = Field(
        None,
        description="The specification for the reference torsion drive calculation, also acts as a provenance source.",
    )
    attenuate_weights: bool = Field(
        False, description="Whether to attenuate the weights as a function of energy."
    )

    energy_denominator: float = Field(
        1.0, description="The energy denominator in objective function contribution."
    )
    energy_cutoff: float = Field(10.0, description="The upper energy cutoff.")

    fit_energy: bool = Field(True, description="Whether to fit to the energy.")
    fit_force: bool = Field(False, description="Whether to fit to the force.")

    @classmethod
    def bespoke_task_type(cls) -> Literal["torsion1d"]:
        return "torsion1d"


class VibrationTargetSchema(BaseTargetSchema):
    """A model which stores information about a vibration fitting target."""

    type: Literal["Vibration"] = "Vibration"

    reference_data: Optional[
        Union[
            LocalQCData[AtomicResult],
            BespokeQCData[HessianTaskSpec],
            BasicResultCollection,
        ]
    ] = Field(
        None,
        description="The reference QC data (either existing or to be generated on the "
        "fly) to fit against.",
    )
    calculation_specification: Optional[HessianTaskSpec] = Field(
        None,
        description="The specification for the reference hessian calculation, also acts as a provenance source.",
    )

    mode_reassignment: Optional[Literal["permute", "overlap"]] = Field(
        None, description="The (optional) method by which to re-assign normal modes."
    )

    @classmethod
    def bespoke_task_type(cls) -> Literal["hessian"]:
        return "hessian"


class OptGeoTargetSchema(BaseTargetSchema):
    """A model which stores information about an optimized geometry fitting target."""

    type: Literal["OptGeo"] = "OptGeo"

    reference_data: Optional[
        Union[
            LocalQCData[OptimizationResult],
            BespokeQCData[OptimizationTaskSpec],
            OptimizationResultCollection,
        ]
    ] = Field(
        None,
        description="The reference QC data (either existing or to be generated on the "
        "fly) to fit against.",
    )
    _reference_data_connectivity = validator("reference_data", allow_reuse=True)(
        _check_connectivity
    )
    calculation_specification: Optional[OptimizationTaskSpec] = Field(
        None,
        description="The specification for the reference optimisation calculation, also acts as a provenance source.",
    )
    bond_denominator: float = Field(
        0.05,
        description="The denominator to scale the contributions of bonds to the "
        "objective function by.",
    )
    angle_denominator: float = Field(
        8.0,
        description="The denominator to scale the contributions of angles to the "
        "objective function by.",
    )
    dihedral_denominator: float = Field(
        0.0,
        description="The denominator to scale the contributions of dihedrals to the "
        "objective function by.",
    )
    improper_denominator: float = Field(
        20.0,
        description="The denominator to scale the contributions of impropers to the "
        "objective function by.",
    )

    @classmethod
    def bespoke_task_type(cls) -> Literal["optimization"]:
        return "optimization"


TargetSchema = Union[
    TorsionProfileTargetSchema,
    AbInitioTargetSchema,
    VibrationTargetSchema,
    OptGeoTargetSchema,
]
