"""
Some utility structures shared through the project.
"""

import abc
from collections import namedtuple
from enum import Enum
from typing import Dict, List, Tuple, Union

import numpy as np
from openforcefield import topology as off
from pydantic import BaseModel, PositiveFloat, constr

from openff.qcsubmit.common_structures import MoleculeAttributes

Task = namedtuple("Task", ["entry", "collection_stage"])


class SchemaBase(BaseModel):
    """
    This is the Schema base class which is adapted to the other schema as required.
    """

    # set any enum fields here to make sure json and yaml work
    _enum_fields = []

    class Config:
        allow_mutation = True
        validate_assignment = True
        json_encoders = {
            np.ndarray: lambda v: v.flatten().tolist(),
            Enum: lambda v: v.value,
        }

    def dict(
        self,
        *,
        include: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
        exclude: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
        by_alias: bool = False,
        skip_defaults: bool = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> "DictStrAny":

        # correct the enum dict rep
        data = super().dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )
        exclude = exclude or []
        for field in self._enum_fields:
            if field not in exclude:
                data[field] = getattr(self, field).value
        return data


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

    parent_molecule: off.Molecule
    parent_torsion: Tuple[int, int]
    fragment_molecule: off.Molecule
    fragment_torsion: Tuple[int, int]
    fragment_attributes: MoleculeAttributes
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
    prior: PositiveFloat = 6.0
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
