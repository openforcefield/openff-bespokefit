import abc
from enum import Enum
from typing import Tuple, Union

from pydantic import BaseModel, PositiveFloat
from typing_extensions import Literal


class SmirksType(str, Enum):
    Bonds = "Bonds"
    Angles = "Angles"
    ProperTorsions = "ProperTorsions"
    ImproperTorsions = "ImproperTorsions"
    Vdw = "vdW"


class ParameterSettings(BaseModel, abc.ABC):
    """A data class to track how the target will effect the target parameters and the
    prior values/ starting values.
    """

    parameter_type: SmirksType
    parameter_subtype: str

    target: str
    prior: PositiveFloat

    class Config:
        validate_assignment = True

    def get_prior(self) -> Tuple[str, PositiveFloat]:
        """Construct a ForceBalance style prior string."""

        prior_string = f"{self.parameter_type}/{self.parameter_subtype}/{self.target}"
        return prior_string, self.prior


class ImproperTorsionSettings(ParameterSettings):

    parameter_type: SmirksType = SmirksType.ImproperTorsions
    parameter_subtype: Literal["Improper"] = "Improper"
    target: Literal["k"] = "k"
    prior: PositiveFloat = 6.0


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
SmirksParameterSettings = Union[
    ProperTorsionSettings,
    BondLengthSettings,
    BondForceSettings,
    AngleForceSettings,
    AngleAngleSettings,
    VdwEpsilonSettings,
    VdwRminHalfSettings,
]
