"""
Some utility structures shared through the project.
"""

from enum import Enum
from typing import Dict, List, Tuple, Union

import numpy as np
from openforcefield import topology as off
from pydantic import BaseModel, PositiveFloat
from typing_extensions import Literal

from openff.qcsubmit.common_structures import MoleculeAttributes


class SchemaBase(BaseModel):
    """
    This is the Schema base class which is adapted to the other schema as required.
    """

    class Config:
        allow_mutation = True
        validate_assignment = True
        arbitrary_types_allowed = True
        json_encoders = {
            np.ndarray: lambda v: v.flatten().tolist(),
            Enum: lambda v: v.value,
        }


class SmirksType(str, Enum):
    ProperTorsions = "ProperTorsions"
    Bonds = "Bonds"
    Angles = "Angles"
    Vdw = "vdW"


class Status(str, Enum):
    Complete = "COMPLETE"
    Optimizing = "OPTIMIZING"
    ErrorCycle = "ErrorCycle"
    ConvergenceError = "CONVERGENCE_ERROR"
    CollectionError = "COLLECTION_ERROR"
    Collecting = "COLLECTING"
    Ready = "READY"
    Prepared = "PREPARED"


class FragmentData(BaseModel):
    """
    A simple dataclass that holds the relation between a parent molecule and the fragment.
    """

    parent_molecule: off.Molecule
    parent_torsion: Tuple[int, int]
    fragment_molecule: off.Molecule
    fragment_torsion: Tuple[int, int]
    fragment_attributes: MoleculeAttributes
    fragment_parent_mapping: Dict[int, int]

    class Config:
        allow_mutation = False
        arbitrary_types_allowed = True

    def fragment_schema(self) -> "FragmentSchema":
        """
        Convert to a fragment schema.
        """
        from openff.bespokefit.schema import FragmentSchema

        schema = FragmentSchema(
            parent_torsion=self.parent_torsion,
            fragment_torsion=self.fragment_torsion,
            fragment_attributes=self.fragment_attributes,
            fragment_parent_mapping=self.fragment_parent_mapping,
        )
        return schema


class ParameterSettings(BaseModel):
    """
    A data class to track how the target will effect the target parameters and the prior values/ starting values.
    """

    parameter_type: SmirksType
    parameter_subtype: str
    target: str
    prior: PositiveFloat

    class Config:
        validate_assignment = True
        arbitrary_types_allowed = True

    def get_prior(self) -> Tuple[str, PositiveFloat]:
        """
        Construct a forcebalance style prior.
        """

        prior_string = f"{self.parameter_type}/{self.parameter_subtype}/{self.target}"
        return prior_string, self.prior

    def dict(self, *args, **kwargs):
        data = super().dict(*args, **kwargs)
        data["parameter_type"] = self.parameter_type.value
        return data


class ProperTorsionSettings(ParameterSettings):

    parameter_type: SmirksType = SmirksType.ProperTorsions
    parameter_subtype: Literal["Proper"] = "Proper"
    target: Literal["k"] = "k"
    prior: PositiveFloat = 6.0


class BondLengthSettings(ParameterSettings):

    parameter_type: Literal[SmirksType.Bonds] = SmirksType.Bonds
    parameter_subtype: Literal["Bond"] = "Bond"
    target: Literal["length"] = "length"
    prior: PositiveFloat = 0.1


class BondForceSettings(BondLengthSettings):

    target: Literal["k"] = "k"
    prior: PositiveFloat = 100


class AngleAngleSettings(ParameterSettings):

    parameter_type: Literal[SmirksType.Angles] = SmirksType.Angles
    parameter_subtype: Literal["Angle"] = "Angle"
    target: Literal["angle"] = "angle"
    prior: PositiveFloat = 10.0


class AngleForceSettings(AngleAngleSettings):

    target: Literal["k"] = "k"
    prior: PositiveFloat = 10.0


class VdwEpsilonSettings(ParameterSettings):

    parameter_type: Literal[SmirksType.Vdw] = SmirksType.Vdw
    parameter_subtype: Literal["Atom"] = "Atom"
    target: Literal["epsilon"] = "epsilon"
    prior: PositiveFloat = 0.1


class VdwRminHalfSettings(VdwEpsilonSettings):

    target: Literal["rmin_half"] = "rmin_half"
    prior: PositiveFloat = 0.1


# define a useful type
SmirksSettings = List[
    Union[
        ProperTorsionSettings,
        BondLengthSettings,
        BondForceSettings,
        AngleForceSettings,
        AngleAngleSettings,
        VdwEpsilonSettings,
        VdwRminHalfSettings,
    ]
]
