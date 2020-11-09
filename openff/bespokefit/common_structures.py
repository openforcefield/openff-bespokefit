"""
Some utility structures shared through the project.
"""

import abc
from collections import namedtuple
from enum import Enum
from typing import Dict, List, Tuple

from openforcefield import topology as off
from pydantic import BaseModel, PositiveFloat, constr

Task = namedtuple("Task", ["entry", "collection_stage"])


class SmirksType(str, Enum):
    ProperTorsions = "ProperTorsions"
    Bonds = "Bonds"
    Angles = "Angles"
    Vdw = "vdW"


class Status(str, Enum):
    Complete = "COMPLETE"
    Optimizing = "OPTIMIZING"
    ConvergenceError = "CONVERGENCE_ERROR"
    CollectionError = "COLLECTION_ERROR"
    Collecting = "COLLECTING"
    Ready = "READY"
    Prepared = "PREPARED"


class FragmentData(BaseModel):
    """
    A simple dataclass that holds the relation between a parent molecule and the fragment.
    """

    # TODO we also need the mapping this can come from fragmenter.

    parent_molecule: off.Molecule
    parent_torsion: Tuple[int, int]
    fragment_molecule: off.Molecule
    fragment_torsion: Tuple[int, int]
    fragment_attributes: Dict[str, str]
    fragment_parent_mapping: Dict[int, int]

    class Config:
        allow_mutation = False
        arbitrary_types_allowed = True


class ParameterSettings(BaseModel, abc.ABC):
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
    parameter_subtype: constr(regex="Proper") = "Proper"
    target: constr(regex="k") = "k"
    prior: PositiveFloat = 1.0
    # allow k values up to k6
    k_values: List[constr(regex="k[1-6]")] = ["k1", "k2", "k3", "k4"]


class BondLengthSettings(ParameterSettings):

    parameter_type: SmirksType = SmirksType.Bonds
    parameter_subtype: constr(regex="Bond") = "Bond"
    target: constr(regex="length") = "length"
    prior: PositiveFloat = 0.1


class BondForceSettings(BondLengthSettings):

    target: constr(regex="k") = "k"
    prior: PositiveFloat = 100


class AngleAngleSettings(ParameterSettings):

    parameter_type: SmirksType = SmirksType.Angles
    parameter_subtype: constr(regex="Angle") = "Angle"
    target: constr(regex="angle") = "angle"
    prior: PositiveFloat = 10.0


class AngleForceSettings(AngleAngleSettings):

    target: constr(regex="k") = "k"
    prior: PositiveFloat = 10.0


class VdwEpsilonSettings(ParameterSettings):

    parameter_type: SmirksType = SmirksType.Vdw
    parameter_subtype: constr(regex="Atom") = "Atom"
    target: constr(regex="epsilon") = "epsilon"
    prior: PositiveFloat = 0.1


class VdwRminHalfSettings(VdwEpsilonSettings):

    target: constr(regex="rmin_half") = "rmin_half"
    prior: PositiveFloat = 0.1
