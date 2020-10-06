import abc
from typing import Dict, Optional, Set, Tuple, Union

from chemper.graphs.environment import ChemicalEnvironment
from openforcefield.typing.engines.smirnoff import (
    AngleHandler,
    BondHandler,
    ImproperTorsionHandler,
    ProperTorsionHandler,
    vdWHandler,
)
from pydantic import validator
from simtk import unit

from ..common_structures import SmirksType
from ..exceptions import SMIRKSTypeError
from ..utils import compare_smirks_graphs
from .schema import SchemaBase


def _to_angstrom(length: float) -> str:
    """
    Take a length value and return the validated version if the unit is missing.
    """
    if isinstance(length, str):
        length = length.split()[0]
    return f"{length} * angstrom"


def _to_degrees(angle: float) -> str:
    if isinstance(angle, str):
        angle = angle.split()[0]
    return f"{angle} * degree"


def _to_bond_force(force: float) -> str:
    if isinstance(force, str):
        force = force.split()[0]
    return f"{force} * angstrom**-2 * mole**-1 * kilocalorie"


def _to_angle_force(force: float) -> str:
    if isinstance(force, str):
        force = force.split()[0]
    return f"{force} * mole**-1 * radian**-2 * kilocalorie"


def _to_kcals_mol(force: float) -> str:
    if isinstance(force, str):
        force = force.split()[0]
    return f"{force} * mole**-1 * kilocalorie"


def _validate_smirks(smirks: str, expected_tags: int) -> str:
    """
    Make sure the supplied smirks has the correct number of tagged atoms.
    """
    smirk = ChemicalEnvironment(smirks=smirks)
    tagged_atoms = len(smirk.get_indexed_atoms())
    if tagged_atoms != expected_tags:
        raise SMIRKSTypeError(
            f"The smirks pattern ({smirks}) has {tagged_atoms} tagged atoms, but should have {expected_tags}."
        )
    else:
        return smirks


class SmirksSchema(SchemaBase):
    """
    This schema identifies new smirks patterns and the corresponding atoms they should be applied to.
    """

    atoms: Set[Tuple[int, ...]]
    smirks: str
    type: SmirksType
    parameterize: Set[str] = set()
    _enum_fields = ["type"]

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

        data = self.dict(exclude={"atoms", "type", "parameterize", "identifier"})
        # now we have to format parameterize
        parameterize = ", ".join(self.parameterize)
        data["parameterize"] = parameterize
        data["allow_cosmetic_attributes"] = True
        return data


class ValidatedSmirks(SmirksSchema, abc.ABC):
    @validator("parameterize")
    def _validate_parameterize(cls, parameters: Set[str]) -> Set[str]:
        """
        Make sure that the fields are valid for the molecule.
        """
        for parameter in parameters:
            if parameter.lower() not in cls.__fields__:
                raise ValueError(
                    f"This smirks does not have a parameter attribute {parameter}"
                )
        return parameters

    @abc.abstractmethod
    def update_parameters(self, off_smirk) -> None:
        """
        Update the parameters of the current smirks pattern using the corresponding openforcefield toolkit smirks class.

        Parameters
        ----------
        off_smirk: Union[BondHandler.BondType, AngleHandler.AngleType, ProperTorsionHandler.ProperTorsionType, ImproperTorsionHandler.ImproperTorsionType, vdWHandler.vdWType]
            The openforcefield parameter type that should be used to extract the parameters from.

        """
        raise NotImplementedError()


class AtomSmirks(ValidatedSmirks):
    """
    Specific atom smirks.
    """

    atoms: Set[Tuple[int]]
    type: SmirksType = SmirksType.Vdw
    epsilon: str
    rmin_half: str

    _validate_epsilion = validator("epsilon", allow_reuse=True)(_to_kcals_mol)
    _validate_sigma = validator("rmin_half", allow_reuse=True)(_to_angstrom)

    @validator("smirks")
    def _validate_smirks(cls, smirks: str) -> str:
        return _validate_smirks(smirks=smirks, expected_tags=1)

    def update_parameters(self, off_smirk: vdWHandler.vdWType) -> None:
        """
        Update the Atom smirks parameter handler using the corresponding openforcefield parameter handler.

        Parameters
        ----------
        off_smirk: vdWHandler.vdWType
            The vdW parameter type that the rmin_half and sigma parameters should extracted from.
        """
        self.epsilon = off_smirk.epsilon.value_in_unit(unit=unit.kilocalorie_per_mole)
        self.rmin_half = off_smirk.rmin_half.value_in_unit(unit.angstroms)


class BondSmirks(ValidatedSmirks):
    atoms: Set[Tuple[int, int]]
    type: SmirksType = SmirksType.Bonds
    k: str
    length: str

    _validate_force = validator("k", allow_reuse=True)(_to_bond_force)
    _validate_length = validator("length", allow_reuse=True)(_to_angstrom)

    @validator("smirks")
    def _validate_smirks(cls, smirks: str) -> str:
        return _validate_smirks(smirks=smirks, expected_tags=2)

    def update_parameters(self, off_smirk: BondHandler.BondType) -> None:
        """
        Update the Bond smirks parameter handler using the corresponding openforcefield parameter handler.

        Parameters
        ----------
        off_smirk: BondHandler.BondType
            The Bond parameter type that the force constant and equilibrium bond length will be extracted from.
        """
        self.k = off_smirk.k.value_in_unit(
            unit=unit.kilocalories_per_mole / unit.angstrom ** 2
        )
        self.length = off_smirk.length.value_in_unit(unit=unit.angstrom)


class AngleSmirks(ValidatedSmirks):
    atoms: Set[Tuple[int, int, int]]
    type: SmirksType = SmirksType.Angles
    k: str
    angle: str

    _validate_force = validator("k", allow_reuse=True)(_to_angle_force)
    _validate_angle = validator("angle", allow_reuse=True)(_to_degrees)

    @validator("smirks")
    def _validate_smirks(cls, smirks: str) -> str:
        return _validate_smirks(smirks=smirks, expected_tags=3)

    def update_parameters(self, off_smirk: AngleHandler.AngleType) -> None:
        """
        Update the Angle smirks parameter handler using the corresponding openforcefield parameter handler.

        Parameters
        ----------
        off_smirk: AngleHandler.AngleType
            The Angle parameter type that the force constant and equilibrium angle will be extracted from.
        """
        self.angle = off_smirk.angle.value_in_unit(unit=unit.degree)
        self.k = off_smirk.k.value_in_unit(
            unit=unit.kilocalorie_per_mole / unit.radian ** 2
        )


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
        self,
        periodicity: str,
        phase: Optional[float] = None,
        k: float = 1e-5,
        idivf: float = 1.0,
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

        data = {"periodicity": periodicity, "phase": phase, "k": k, "idivf": idivf}
        super().__init__(**data)


class TorsionSmirks(SmirksSchema):
    atoms: Set[Tuple[int, int, int, int]]
    type: SmirksType = SmirksType.ProperTorsions
    terms: Dict[str, TorsionTerm] = {}

    @validator("smirks")
    def _validate_smirks(cls, smirks: str) -> str:
        return _validate_smirks(smirks=smirks, expected_tags=4)

    @validator("parameterize")
    def _validate_ks(cls, parameters: Set[str]) -> Set[str]:
        "Make sure K values are specified"
        allowed_values = ["k1", "k2", "k3", "k4", "k5", "k6"]
        for parameter in parameters:
            if parameter not in allowed_values:
                raise ValueError(
                    f"The parameter {parameter} is not supported for parametrization."
                )
        return parameters

    def update_parameters(
        self,
        off_smirk: Union[
            ProperTorsionHandler.ProperTorsionType,
            ImproperTorsionHandler.ImproperTorsionType,
        ],
    ) -> None:
        """
        Update the Torsion smirks parameter handler using the corresponding openforcefield parameter handler.

        Parameters
        ----------
        off_smirk: Union[ProperTorsionHandler.ProperTorsionType, ImproperTorsionHandler.ImproperTorsionType]
            The Torsion parameter type that the parameters should be extracted from.
        """
        # clear out the current terms as the number of k could change
        self.terms = {}
        for i, p in enumerate(off_smirk.periodicity):
            new_term = TorsionTerm(
                periodicity=p,
                phase=off_smirk.phase[i].value_in_unit(unit=unit.degree),
                idivf=off_smirk.idivf[i],
                k=off_smirk.k[i].value_in_unit(unit=unit.kilocalorie_per_mole),
            )
            self.add_torsion_term(term=new_term)

    def add_torsion_term(self, term: Union[str, TorsionTerm]) -> None:
        if isinstance(term, str):
            # make a torsion term and add it
            periodicity = term.split("k")[-1]
            new_term = TorsionTerm(periodicity=periodicity)
        else:
            new_term = term

        self.terms[new_term.periodicity] = new_term

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
