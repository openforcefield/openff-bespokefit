import abc
from typing import Set, Union

from pydantic import Field, validator
from typing_extensions import Literal

from openff.bespokefit.utilities.pydantic import SchemaBase
from openff.bespokefit.utilities.smirks import validate_smirks


class BaseSmirksParameter(SchemaBase, abc.ABC):
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
    def _expected_n_tags(cls) -> int:
        raise NotImplementedError()

    @validator("smirks")
    def _check_smirks(cls, value: str) -> str:
        return validate_smirks(value, cls._expected_n_tags())


class VdWSmirks(BaseSmirksParameter):

    type: Literal["vdW"] = "vdW"

    attributes: Set[Literal["epsilon", "sigma"]] = Field(
        ..., description="The attributes of the parameter which should be optimized."
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 1


class BondSmirks(BaseSmirksParameter):

    type: Literal["Bonds"] = "Bonds"

    attributes: Set[Literal["k", "length"]] = Field(
        ..., description="The attributes of the parameter which should be optimized."
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 2


class AngleSmirks(BaseSmirksParameter):

    type: Literal["Angles"] = "Angles"

    attributes: Set[Literal["k", "angle"]] = Field(
        ..., description="The attributes of the parameter which should be optimized."
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 3


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


class ProperTorsionSmirks(BaseSmirksParameter):
    type: Literal["ProperTorsions"] = "ProperTorsions"

    attributes: Set[Literal[ProperTorsionAttribute]] = Field(
        ..., description="The attributes of the parameter which should be optimized."
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 4


# fmt: off
ImproperTorsionAttribute = Literal[
    "k*", "periodicity*", "phase*", "idivf*",
    "k1", "periodicity1", "phase1", "idivf1",
    "k2", "periodicity2", "phase2", "idivf2",
    "k3", "periodicity3", "phase3", "idivf3",
    "k4", "periodicity4", "phase4", "idivf4",
]


class ImproperTorsionSmirks(BaseSmirksParameter):
    type: Literal["ImproperTorsions"] = "ImproperTorsions"

    attributes: Set[Literal[ImproperTorsionAttribute]] = Field(
        ..., description="The attributes of the parameter which should be optimized."
    )

    @classmethod
    def _expected_n_tags(cls) -> int:
        return 4


SmirksParameter = Union[
    VdWSmirks,
    BondSmirks,
    AngleSmirks,
    ProperTorsionSmirks,
    ImproperTorsionSmirks,
]
