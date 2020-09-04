from typing import Dict, Optional, Set, Tuple, Union

from pydantic import validator

from ..common_structures import SmirksType
from ..utils import compare_smirks_graphs
from .schema import SchemaBase


def _to_angstrom(length: float) -> str:
    """
    Take a length value and return the validated version if the unit is missing.
    """
    return f"{length} * angstrom"


def _to_degrees(angle: float) -> str:
    return f"{angle} * degree"


def _to_bond_force(force: float) -> str:
    return f"{force} * angstroms**2 * mole**-1 * kilocalrie"


def _to_angle_force(force: float) -> str:
    return f"{force} * mole**-1 * radian**-2 * kilocalorie"


def _to_kcals_mol(force: float) -> str:
    return f"{force} * mole**-1 * kilocalorie"


class SmirksSchema(SchemaBase):
    """
    This schema identifies new smirks patterns and the corresponding atoms they should be applied to.
    """

    atoms: Set[Tuple[int, ...]]
    smirks: str
    type: SmirksType
    parameterize: Set[str] = {}

    def __eq__(self, other: "SmirksSchema"):
        """
        Compare two smirks patterns and determine if they are equivalent.
        First we compare the string if they do not match we have to do a graph isomorphic check specific to the parameter type.
        """
        if self.type == other.type:
            return compare_smirks_graphs(self.smirks, other.smirks)
        else:
            return False

    def to_off_smirks(self) -> Dict[str, str]:
        """
        Construct a dictionary that can be made into an OpenFF parameter.
        """

        data = self.dict(exclude={"atoms", "type", "parameterize"})
        # now we have to format parameterize
        parameterize = ", ".join(self.parameterize)
        data["parameterize"] = parameterize
        data["allow_cosmetic_attributes"] = True
        return data


class ValidatedSmirks(SmirksSchema):
    @validator("parameterize", each_item=True)
    def validate_parameterize(cls, parameter: str) -> str:
        """
        Make sure that the fields are valid for the molecule.
        """
        if parameter.lower() in cls.__fields__:
            return parameter.lower()
        else:
            raise ValueError(
                f"This smirks does not correspond to the parameter attribute  {parameter}"
            )


class AtomSmirks(ValidatedSmirks):
    """
    Specific atom smirks.
    """

    atoms: Set[Tuple[int]]
    type: SmirksType = SmirksType.Vdw
    epsilon: str
    sigma: str

    _validate_epsilion = validator("epsilon", allow_reuse=True)(_to_kcals_mol)
    _validate_sigma = validator("sigma", allow_reuse=True)(_to_angstrom)


class BondSmirks(ValidatedSmirks):
    atoms: Set[Tuple[int, int]]
    type: SmirksType = SmirksType.Bonds
    k: str
    length: str

    _validate_force = validator("k", allow_reuse=True)(_to_bond_force)
    _validate_length = validator("length", allow_reuse=True)(_to_angstrom)


class AngleSmirks(ValidatedSmirks):
    atoms: Set[Tuple[int, int, int]]
    type: SmirksType = SmirksType.Angles
    k: str
    angle: str

    _validate_force = validator("k", allow_reuse=True)(_to_angle_force)
    _validate_angle = validator("angle", allow_reuse=True)(_to_degrees)


class TorsionTerm(SchemaBase):
    periodicity: str
    phase: str
    k: str
    idivf: str = "1.0"

    @validator("periodicity")
    def _validate_periodicity(cls, p: str) -> str:
        if 1 <= int(p) <= 6:
            return p
        else:
            raise ValueError(f"Periodicity must be between 1 and 6.")

    _validate_phase = validator("phase", allow_reuse=True)(_to_degrees)
    _validate_force = validator("k", allow_reuse=True)(_to_kcals_mol)

    def __init__(
        self, periodicity: str, phase: Optional[float] = None, force: float = 1e-5
    ):
        """
        Here we can build a dummy term from the periodicity.
        """
        if phase is None:
            # work out the phase from the periodicity
            if int(periodicity) % 2 == 1:
                phase = 0
            else:
                phase = 180

        data = {"periodicity": periodicity, "phase": phase, "k": force}
        super().__init__(**data)


class TorsionSmirks(SmirksSchema):
    atoms: Set[Tuple[int, int, int, int]]
    type: SmirksType = SmirksType.ProperTorsions
    terms: Dict[str, TorsionTerm] = {}

    def add_torsion_term(self, term: Union[str, TorsionTerm]) -> None:
        if isinstance(term, str):
            # make a torsion term and add it
            periodicity = term.split("k")[-1]
            new_term = TorsionTerm(periodicity=periodicity)
        else:
            new_term = term

        self.terms[new_term.periodicity] = new_term

    @validator("parameterize", each_item=True, pre=True)
    def validate_ks(cls, parameter) -> str:
        "Make sure K values are specified"
        allowed_values = ["k1", "k2", "k3", "k4", "k5", "k6"]
        if parameter in allowed_values:
            return parameter
        else:
            raise ValueError(
                f"The parameter {parameter} is not supported for parametrization."
            )

    def to_off_smirks(self) -> Dict[str, str]:
        """
        Construct a dictionary that can be converted into an OpenFF parameter type.
        Here we have to construct the correct periodicity, phase and force flags.
        """

        data = {
            "smirks": self.smirks,
            "allow_cosmetic_attributes": True,
        }
        # now we have to format parameterize
        parameterize = ", ".join(self.parameterize)
        data["parameterize"] = parameterize
        # now for each term we have to expand them out and correct the tags
        for value, term in self.terms.items():
            term_data = term.dict()
            corrected_data = {
                (name + value, param) for name, param in term_data.items()
            }
            data.update(corrected_data)

        return data
