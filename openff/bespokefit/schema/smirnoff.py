"""Schema for SMIRNOFF parameters."""

import abc
from typing import Literal, Union

from chemper.graphs.environment import ChemicalEnvironment
from openff.toolkit.typing.engines.smirnoff import (
    AngleHandler,
    BondHandler,
    ImproperTorsionHandler,
    ParameterType,
    ProperTorsionHandler,
    vdWHandler,
)
from pydantic import Field, PositiveFloat, validator

from openff.bespokefit.utilities.pydantic import SchemaBase


def validate_smirks(smirks: str, expected_tags: int) -> str:
    """Make sure the supplied smirks has the correct number of tagged atoms."""
    smirk = ChemicalEnvironment(smirks=smirks)
    tagged_atoms = len(smirk.get_indexed_atoms())

    assert tagged_atoms == expected_tags, (
        f"The smirks pattern ({smirks}) has {tagged_atoms} tagged atoms, but should "
        f"have {expected_tags}."
    )

    return smirks


class BaseSMIRKSParameter(SchemaBase, abc.ABC):
    """Identify new smirks patterns and the corresponding atoms they should be applied to."""

    type: Literal["base"] = "base"

    smirks: str = Field(
        ...,
        description="The SMIRKS pattern that defines which chemical environment the "
        "parameter should be applied to.",
    )

    attributes: set[str] = Field(
        ...,
        description="The attributes of the parameter which should be optimized.",
    )

    cached: bool = Field(
        False,
        description="If the parameter was reused from a local cache rather than fit.",
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
        """Create a version of this class from a SMIRNOFF parameter."""

    def __eq__(self, other):
        return type(self) is type(other) and self.__hash__() == other.__hash__()

    def __ne__(self, other):
        assert not self.__eq__(other)

    def __hash__(self):
        return hash((self.type, self.smirks, self.cached, tuple(self.attributes)))


class BaseSMIRKSHyperparameters(SchemaBase, abc.ABC):
    """Track how the target will effect the target parameters and the prior values/ starting values."""

    type: Literal["base"] = "base"

    priors: dict[str, PositiveFloat] = Field(..., description="")

    @classmethod
    @abc.abstractmethod
    def offxml_tag(cls) -> str:
        """Return the OFFXML tag that wraps this parameter type."""
        raise NotImplementedError()


class VdWSMIRKS(BaseSMIRKSParameter):
    """SMIRKS patterns for vdW interactions."""

    type: Literal["vdW"] = "vdW"

    attributes: set[Literal["epsilon", "sigma"]] = Field(
        ...,
        description="The attributes of the parameter which should be optimized.",
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 1

    @classmethod
    def from_smirnoff(cls, parameter: vdWHandler.vdWType) -> "VdWSMIRKS":
        """Create a version of this class from a SMIRNOFF parameter."""
        return cls(
            smirks=parameter.smirks,
            attributes={"epsilon", "sigma"},
            cached=getattr(parameter, "_cached", False),
        )


class VdWHyperparameters(BaseSMIRKSHyperparameters):
    """Hyperparameters for vdW terms."""

    type: Literal["vdW"] = "vdW"

    priors: dict[Literal["epsilon", "sigma"], PositiveFloat] = Field(
        {"epsilon": 0.1, "sigma": 0.1},
        description="",
    )

    @classmethod
    def offxml_tag(cls) -> str:
        """Return the OFFXML tag that wraps this parameter type."""
        return "Atom"


class BondSMIRKS(BaseSMIRKSParameter):
    """SMIRKS patterns for harmonic bonds."""

    type: Literal["Bonds"] = "Bonds"

    attributes: set[Literal["k", "length"]] = Field(
        ...,
        description="The attributes of the parameter which should be optimized.",
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 2

    @classmethod
    def from_smirnoff(cls, parameter: BondHandler.BondType) -> "BondSMIRKS":
        """Create a version of this class from a SMIRNOFF parameter."""
        return cls(
            smirks=parameter.smirks,
            attributes={"k", "length"},
            cached=getattr(parameter, "_cached", False),
        )


class BondHyperparameters(BaseSMIRKSHyperparameters):
    """Hyperparameters for harmonic bonds."""

    type: Literal["Bonds"] = "Bonds"

    priors: dict[Literal["k", "length"], PositiveFloat] = Field(
        {"k": 100.0, "length": 0.1},
        description="",
    )

    @classmethod
    def offxml_tag(cls) -> str:
        """Return the OFFXML tag that wraps this parameter type."""
        return "Bond"


class AngleSMIRKS(BaseSMIRKSParameter):
    """SMIRKS patterns for harmonic angles."""

    type: Literal["Angles"] = "Angles"

    attributes: set[Literal["k", "angle"]] = Field(
        ...,
        description="The attributes of the parameter which should be optimized.",
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 3

    @classmethod
    def from_smirnoff(cls, parameter: AngleHandler.AngleType) -> "AngleSMIRKS":
        """Create a version of this class from a SMIRNOFF parameter."""
        return cls(
            smirks=parameter.smirks,
            attributes={"k", "angle"},
            cached=getattr(parameter, "_cached", False),
        )


class AngleHyperparameters(BaseSMIRKSHyperparameters):
    """Hyperparameters for harmonic angles."""

    type: Literal["Angles"] = "Angles"

    priors: dict[Literal["k", "angle"], PositiveFloat] = Field(
        {"k": 10.0, "angle": 10.0},
        description="",
    )

    @classmethod
    def offxml_tag(cls) -> str:
        """Return the OFFXML tag that wraps this parameter type."""
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
    """SMIRKS patterns for proper torsions."""

    type: Literal["ProperTorsions"] = "ProperTorsions"

    attributes: set[Literal[ProperTorsionAttribute]] = Field(
        ..., description="The attributes of the parameter which should be optimized.",
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 4

    @classmethod
    def from_smirnoff(
        cls, parameter: ProperTorsionHandler.ProperTorsionType,
    ) -> "ProperTorsionSMIRKS":
        """Create a version of this class from a SMIRNOFF parameter."""
        return cls(
            smirks=parameter.smirks,
            attributes={f"k{i + 1}" for i in range(len(parameter.k))},
            # cosmetic attrs are hidden
            cached=getattr(parameter, "_cached", False),
        )


class ProperTorsionHyperparameters(BaseSMIRKSHyperparameters):
    """Hyperparameters for proper torsions."""

    type: Literal["ProperTorsions"] = "ProperTorsions"

    priors: dict[ProperTorsionAttribute, PositiveFloat] = Field(
        {"k": 6.0}, description="",
    )

    @classmethod
    def offxml_tag(cls) -> str:
        """Return the OFFXML tag that wraps this parameter type."""
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
    """SMIRKS patterns for improper torsions."""

    type: Literal["ImproperTorsions"] = "ImproperTorsions"

    attributes: set[Literal[ImproperTorsionAttribute]] = Field(
        ..., description="The attributes of the parameter which should be optimized.",
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 4

    @classmethod
    def from_smirnoff(
        cls, parameter: ImproperTorsionHandler.ImproperTorsionType,
    ) -> "ImproperTorsionSMIRKS":
        """Create a version of this class from a SMIRNOFF parameter."""
        raise NotImplementedError()


class ImproperTorsionHyperparameters(BaseSMIRKSHyperparameters):
    """Hyperparameters for improper torsions."""

    type: Literal["ImproperTorsions"] = "ImproperTorsions"

    priors: dict[ProperTorsionAttribute, PositiveFloat] = Field(
        {"k": 6.0}, description="",
    )

    @classmethod
    def offxml_tag(cls) -> str:
        """Return the OFFXML tag that wraps this parameter type."""
        return "Improper"


SMIRNOFFParameter = Union[
    VdWSMIRKS, BondSMIRKS, AngleSMIRKS, ProperTorsionSMIRKS, ImproperTorsionSMIRKS,
]
SMIRNOFFHyperparameters = Union[
    ProperTorsionHyperparameters,
    BondHyperparameters,
    AngleHyperparameters,
    VdWHyperparameters,
    ImproperTorsionHyperparameters,
]


def get_smirnoff_parameter(parameter_type: str) -> type[SMIRNOFFParameter]:
    """Get the SMIRNOFFParameter class from the parameter type."""
    _parameters_by_type = {
        VdWSMIRKS.__fields__["type"].default: VdWSMIRKS,
        BondSMIRKS.__fields__["type"].default: BondSMIRKS,
        AngleSMIRKS.__fields__["type"].default: AngleSMIRKS,
        ProperTorsionSMIRKS.__fields__["type"].default: ProperTorsionSMIRKS,
        ImproperTorsionSMIRKS.__fields__["type"].default: ImproperTorsionSMIRKS,
    }
    return _parameters_by_type[parameter_type]
