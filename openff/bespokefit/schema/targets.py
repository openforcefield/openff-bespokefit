import abc
from typing import Any, Dict, Optional, Union

from openff.qcsubmit.results import (
    BasicResultCollection,
    OptimizationResultCollection,
    TorsionDriveResultCollection,
)
from openff.toolkit.topology import Molecule
from pydantic import Field, PositiveFloat
from qcelemental.models import AtomicResult
from qcelemental.models import Molecule as QCEMolecule
from qcelemental.models.procedures import (
    OptimizationResult,
    TorsionDriveResult,
)
from qcelemental.molutil import guess_connectivity
from typing_extensions import Literal
from openff.bespokefit.exceptions import TargetConnectivityChanged

from openff.bespokefit.schema.data import BespokeQCData, LocalQCData
from openff.bespokefit.schema.tasks import (
    HessianTaskSpec,
    OptimizationTaskSpec,
    Torsion1DTaskSpec,
)
from openff.bespokefit.utilities.pydantic import SchemaBase


def _check_connectivity(
    qcschema: QCEMolecule,
    name: str,
    fragment: Optional[Molecule] = None,
):
    """
    Raise an exception if the geometry of ``qcschema`` does not match ``fragment``

    Parameters
    ==========

    qcschema
        A QCElemental ``Molecule`` representing the final geometry of a QC
        computation
    name
        A name for the current calculation. Used in the exception raised by this
        method.
    fragment
        An OpenFF ``Molecule`` representing the true chemical identity of the
        fragment.

    Returns
    =======

    None

    Raises
    ======

    ValueError
        If the connectivity does not match.
    """
    # If expected connectivity is not provided, compute it from the fragment
    if fragment is None:
        fragment = Molecule.from_qcschema(qcschema)

    # Get expected connectivity from bonds
    expected_connectivity = {
        tuple(sorted([bond.atom1_index + 1, bond.atom2_index + 1]))
        for bond in fragment.bonds
    }

    # Guess found connectivity from the output geometry
    actual_connectivity = {
        tuple(sorted([a + 1, b + 1]))
        for a, b in guess_connectivity(qcschema.symbols, qcschema.geometry)
    }

    if expected_connectivity != actual_connectivity:
        raise TargetConnectivityChanged(
            record_name=name,
            fragment_smiles=fragment.to_smiles(mapped=True),
            missing_connections=expected_connectivity - actual_connectivity,
            unexpected_connections=actual_connectivity - expected_connectivity,
            geometry=qcschema.geometry,
        )


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

    def validate_reference_data(self) -> None:
        """
        Perform any required validations on the reference data.

        We don't use Pydantic for this because it doesn't play nice with JSON
        errors. Successfuly validation returns ``None``; unsuccessful
        validation raises an error. The default implementation checks that
        connectivity is unchanged after QM calculations; if this is not desired
        in a subclass, override this method.
        """
        self._validate_connectivity()

    def _validate_connectivity(
        self,
    ):
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
        ref_data = self.reference_data
        if ref_data is None or isinstance(ref_data, BespokeQCData):
            # Reference data has not been computed, so the connectivity is intact
            return
        elif isinstance(ref_data, LocalQCData):
            for qc_record in ref_data.qc_records:
                # Some qc records (eg, TorsionDriveResult) use .final_molecules (plural),
                # others (eg, OptimizationResult) use .final_molecule (singular)
                try:
                    final_molecules = qc_record.final_molecules
                except AttributeError:
                    final_molecules = {"opt": qc_record.final_molecule}

                for name, qcschema in final_molecules.items():
                    _check_connectivity(qcschema, name)
        elif hasattr(ref_data, "to_records"):
            # Reference data is a QCSubmit result collection
            for qc_record, fragment in ref_data.to_records():
                # Some qc records (eg, TorsionDriveRecord) use .get_final_molecules() (plural),
                # others (eg, OptimizationRecord) use .get_final_molecule() (singular)
                try:
                    final_molecules = qc_record.get_final_molecules()
                except AttributeError:
                    final_molecules = {"opt": qc_record.get_final_molecule()}

                for name, qcschema in final_molecules.items():
                    _check_connectivity(qcschema, name, fragment)


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

    def validate_reference_data(self) -> None:
        """
        Vibrations (currently) perform no geometry optimization, so no validation is necessary.
        """
        return None


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
