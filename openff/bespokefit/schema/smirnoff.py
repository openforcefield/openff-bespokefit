import abc
from typing import Dict, Set, Union

from openff.toolkit.typing.engines.smirnoff import (
    AngleHandler,
    BondHandler,
    ImproperTorsionHandler,
    ParameterType,
    ProperTorsionHandler,
    vdWHandler,
)
from pydantic import Field, PositiveFloat, validator
from typing_extensions import Literal

from openff.bespokefit.utilities.pydantic import SchemaBase
from openff.bespokefit.utilities.smirks import validate_smirks


class BaseSMIRKSParameter(SchemaBase, abc.ABC):
    """
    This schema identifies new smirks patterns and the corresponding atoms they should
    be applied to.
    """

    type: Literal["base"] = "base"

    smirks: str = Field(
        ...,
        description="The SMIRKS pattern that defines which chemical environment the "
        "parameter should be applied to.",
    )

    attributes: Set[str] = Field(
        ..., description="The attributes of the parameter which should be optimized."
    )

    @classmethod
    @abc.abstractmethod
    def _expected_n_tags(cls) -> int:
        raise NotImplementedError()

    @validator("smirks")
    def _check_smirks(cls, value: str) -> str:
        return validate_smirks(value, cls._expected_n_tags())

    @classmethod
    @abc.abstractmethod
    def from_smirnoff(cls, parameter: ParameterType):
        """Creates a version of this class from a SMIRNOFF parameter"""

    def __eq__(self, other):
        return type(self) == type(other) and self.__hash__() == other.__hash__()

    def __ne__(self, other):
        assert not self.__eq__(other)

    def __hash__(self):
        return hash((self.type, self.smirks, tuple(self.attributes)))


class BaseSMIRKSHyperparameters(SchemaBase, abc.ABC):
    """A data class to track how the target will effect the target parameters and the
    prior values/ starting values.
    """

    type: Literal["base"] = "base"

    priors: Dict[str, PositiveFloat] = Field(..., description="")

    @classmethod
    @abc.abstractmethod
    def offxml_tag(cls) -> str:
        """The OFFXML tag that wraps this parameter type."""
        raise NotImplementedError()


class VdWSMIRKS(BaseSMIRKSParameter):

    type: Literal["vdW"] = "vdW"

    attributes: Set[Literal["epsilon", "sigma"]] = Field(
        ..., description="The attributes of the parameter which should be optimized."
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 1

    @classmethod
    def from_smirnoff(cls, parameter: vdWHandler.vdWType) -> "VdWSMIRKS":
        return cls(smirks=parameter.smirks, attributes={"epsilon", "sigma"})


class VdWHyperparameters(BaseSMIRKSHyperparameters):

    type: Literal["vdW"] = "vdW"

    priors: Dict[Literal["epsilon", "sigma"], PositiveFloat] = Field(
        {"epsilon": 0.1, "sigma": 0.1}, description=""
    )

    @classmethod
    def offxml_tag(cls) -> str:
        return "Atom"


class BondSMIRKS(BaseSMIRKSParameter):

    type: Literal["Bonds"] = "Bonds"

    attributes: Set[Literal["k", "length"]] = Field(
        ..., description="The attributes of the parameter which should be optimized."
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 2

    @classmethod
    def from_smirnoff(cls, parameter: BondHandler.BondType) -> "BondSMIRKS":
        return cls(smirks=parameter.smirks, attributes={"k", "length"})


class BondHyperparameters(BaseSMIRKSHyperparameters):

    type: Literal["Bonds"] = "Bonds"

    priors: Dict[Literal["k", "length"], PositiveFloat] = Field(
        {"k": 100.0, "length": 0.1}, description=""
    )

    @classmethod
    def offxml_tag(cls) -> str:
        return "Bond"


class AngleSMIRKS(BaseSMIRKSParameter):

    type: Literal["Angles"] = "Angles"

    attributes: Set[Literal["k", "angle"]] = Field(
        ..., description="The attributes of the parameter which should be optimized."
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 3

    @classmethod
    def from_smirnoff(cls, parameter: AngleHandler.AngleType) -> "AngleSMIRKS":
        return cls(smirks=parameter.smirks, attributes={"k", "angle"})


class AngleHyperparameters(BaseSMIRKSHyperparameters):

    type: Literal["Angles"] = "Angles"

    priors: Dict[Literal["k", "length"], PositiveFloat] = Field(
        {"k": 10.0, "angle": 10.0}, description=""
    )

    @classmethod
    def offxml_tag(cls) -> str:
        return "Angle"


# TODO: This can likely be more cleanly handled by a pydantic regex type.
# fmt: off
ProperTorsionAttribute = Literal[
    "k", "k1_bondorder", "k1_bondorder", "periodicity", "phase", "idivf",
    "k1", "k1_bondorder1", "k1_bondorder2", "periodicity1", "phase1", "idivf1",
    "k2", "k2_bondorder1", "k2_bondorder2", "periodicity2", "phase2", "idivf2",
    "k3", "k3_bondorder1", "k3_bondorder2", "periodicity3", "phase3", "idivf3",
    "k4", "k4_bondorder1", "k4_bondorder2", "periodicity4", "phase4", "idivf4",
    "k5", "k5_bondorder1", "k5_bondorder2", "periodicity5", "phase5", "idivf5",
    "k6", "k6_bondorder1", "k6_bondorder2", "periodicity6", "phase6", "idivf6",
]


class ProperTorsionSMIRKS(BaseSMIRKSParameter):

    type: Literal["ProperTorsions"] = "ProperTorsions"

    attributes: Set[Literal[ProperTorsionAttribute]] = Field(
        ..., description="The attributes of the parameter which should be optimized."
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 4

    @classmethod
    def from_smirnoff(
        cls, parameter: ProperTorsionHandler.ProperTorsionType
    ) -> "ProperTorsionSMIRKS":

        return cls(
            smirks=parameter.smirks,
            attributes={f"k{i + 1}" for i in range(len(parameter.k))}
        )


class ProperTorsionHyperparameters(BaseSMIRKSHyperparameters):

    type: Literal["ProperTorsions"] = "ProperTorsions"

    priors: Dict[ProperTorsionAttribute, PositiveFloat] = Field(
        {"k": 6.0}, description=""
    )

    @classmethod
    def offxml_tag(cls) -> str:
        return "Proper"


# fmt: off
ImproperTorsionAttribute = Literal[
    "k*", "periodicity*", "phase*", "idivf*",
    "k1", "periodicity1", "phase1", "idivf1",
    "k2", "periodicity2", "phase2", "idivf2",
    "k3", "periodicity3", "phase3", "idivf3",
    "k4", "periodicity4", "phase4", "idivf4",
]


class ImproperTorsionSMIRKS(BaseSMIRKSParameter):
    type: Literal["ImproperTorsions"] = "ImproperTorsions"

    attributes: Set[Literal[ImproperTorsionAttribute]] = Field(
        ..., description="The attributes of the parameter which should be optimized."
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 4

    @classmethod
    def from_smirnoff(
        cls, parameter: ImproperTorsionHandler.ImproperTorsionType
    ) -> "ImproperTorsionSMIRKS":
        raise NotImplementedError()


class ImproperTorsionHyperparameters(BaseSMIRKSHyperparameters):

    type: Literal["ImproperTorsions"] = "ImproperTorsions"

    priors: Dict[ProperTorsionAttribute, PositiveFloat] = Field(
        {"k": 6.0}, description=""
    )

    @classmethod
    def offxml_tag(cls) -> str:
        return "Improper"


SMIRNOFFParameter = Union[
    VdWSMIRKS, BondSMIRKS, AngleSMIRKS, ProperTorsionSMIRKS, ImproperTorsionSMIRKS
]
SMIRNOFFHyperparameters = Union[
    ProperTorsionHyperparameters,
    BondHyperparameters,
    AngleHyperparameters,
    VdWHyperparameters,
    ImproperTorsionHyperparameters,
]
