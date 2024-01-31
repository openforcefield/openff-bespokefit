import numpy as np
from ..molparse.from_arrays import from_arrays as from_arrays
from ..molparse.from_schema import from_schema as from_schema
from ..molparse.from_string import from_string as from_string
from ..molparse.to_schema import to_schema as to_schema
from ..molparse.to_string import to_string as to_string
from ..periodic_table import periodictable as periodictable
from ..physical_constants import constants as constants
from ..testing import compare as compare, compare_values as compare_values
from ..util import deserialize as deserialize, measure_coordinates as measure_coordinates, msgpackext_loads as msgpackext_loads, provenance_stamp as provenance_stamp, which_import as which_import
from .basemodels import ProtoModel as ProtoModel, qcschema_draft as qcschema_draft
from .common_models import Provenance as Provenance, qcschema_molecule_default as qcschema_molecule_default
from .types import Array as Array
from _typeshed import Incomplete
from pydantic import ConstrainedFloat, ConstrainedInt, constr as constr
from pydantic.typing import ReprArgs as ReprArgs
from typing import Any, Dict, List, Optional, Tuple, Union

GEOMETRY_NOISE: int
MASS_NOISE: int
CHARGE_NOISE: int

def float_prep(array, around): ...

class NonnegativeInt(ConstrainedInt):
    ge: int

class BondOrderFloat(ConstrainedFloat):
    ge: int
    le: int

class Identifiers(ProtoModel):
    molecule_hash: Optional[str]
    molecular_formula: Optional[str]
    smiles: Optional[str]
    inchi: Optional[str]
    inchikey: Optional[str]
    canonical_explicit_hydrogen_smiles: Optional[str]
    canonical_isomeric_explicit_hydrogen_mapped_smiles: Optional[str]
    canonical_isomeric_explicit_hydrogen_smiles: Optional[str]
    canonical_isomeric_smiles: Optional[str]
    canonical_smiles: Optional[str]
    pubchem_cid: Optional[str]
    pubchem_sid: Optional[str]
    pubchem_conformerid: Optional[str]
    class Config(ProtoModel.Config):
        serialize_skip_defaults: bool

class Molecule(ProtoModel):
    schema_name: None
    schema_version: int
    validated: bool
    symbols: Array[str]
    geometry: Array[float]
    name: Optional[str]
    identifiers: Optional[Identifiers]
    comment: Optional[str]
    molecular_charge: float
    molecular_multiplicity: int
    masses_: Optional[Array[float]]
    real_: Optional[Array[bool]]
    atom_labels_: Optional[Array[str]]
    atomic_numbers_: Optional[Array[np.int16]]
    mass_numbers_: Optional[Array[np.int16]]
    connectivity_: Optional[List[Tuple[NonnegativeInt, NonnegativeInt, BondOrderFloat]]]
    fragments_: Optional[List[Array[np.int32]]]
    fragment_charges_: Optional[List[float]]
    fragment_multiplicities_: Optional[List[int]]
    fix_com: bool
    fix_orientation: bool
    fix_symmetry: Optional[str]
    provenance: Provenance
    id: Optional[Any]
    extras: Dict[str, Any]
    class Config(ProtoModel.Config):
        serialize_skip_defaults: bool
        repr_style: Incomplete
        fields: Incomplete
        def schema_extra(schema, model) -> None: ...
    def __init__(self, orient: bool = False, validate: Optional[bool] = None, **kwargs: Any) -> None: ...
    @property
    def hash_fields(self): ...
    @property
    def masses(self) -> Array[float]: ...
    @property
    def real(self) -> Array[bool]: ...
    @property
    def atom_labels(self) -> Array[str]: ...
    @property
    def atomic_numbers(self) -> Array[np.int16]: ...
    @property
    def mass_numbers(self) -> Array[np.int16]: ...
    @property
    def connectivity(self) -> List[Tuple[int, int, float]]: ...
    @property
    def fragments(self) -> List[Array[np.int32]]: ...
    @property
    def fragment_charges(self) -> List[float]: ...
    @property
    def fragment_multiplicities(self) -> List[int]: ...
    def show(self, ngl_kwargs: Optional[Dict[str, Any]] = None) -> nglview.NGLWidget: ...
    def measure(self, measurements: Union[List[int], List[List[int]]], *, degrees: bool = True) -> Union[float, List[float]]: ...
    def orient_molecule(self): ...
    def compare(self, other): ...
    def __eq__(self, other): ...
    def dict(self, *args, **kwargs): ...
    def pretty_print(self): ...
    def get_fragment(self, real: Union[int, List], ghost: Optional[Union[int, List]] = None, orient: bool = False, group_fragments: bool = True) -> Molecule: ...
    def to_string(self, dtype: str, units: str = None, *, atom_format: str = None, ghost_format: str = None, width: int = 17, prec: int = 12, return_data: bool = False): ...
    def get_hash(self): ...
    def get_molecular_formula(self, order: str = 'alphabetical') -> str: ...
    @classmethod
    def from_data(cls, data: Union[str, Dict[str, Any], np.ndarray, bytes], dtype: Optional[str] = None, *, orient: bool = False, validate: bool = None, **kwargs: Dict[str, Any]) -> Molecule: ...
    @classmethod
    def from_file(cls, filename: str, dtype: Optional[str] = None, *, orient: bool = False, **kwargs): ...
    def to_file(self, filename: str, dtype: Optional[str] = None) -> None: ...
    def __repr_args__(self) -> ReprArgs: ...
    def nuclear_repulsion_energy(self, ifr: int = None) -> float: ...
    def nelectrons(self, ifr: int = None) -> int: ...
    def align(self, ref_mol: Molecule, *, do_plot: bool = False, verbose: int = 0, atoms_map: bool = False, run_resorting: bool = False, mols_align: Union[bool, float] = False, run_to_completion: bool = False, uno_cutoff: float = 0.001, run_mirror: bool = False, generic_ghosts: bool = False) -> Tuple['Molecule', Dict[str, Any]]: ...
    def scramble(self, *, do_shift: Union[bool, Array[float], List] = True, do_rotate: Union[bool, Array[float], List[List]] = True, do_resort: Union[bool, List] = True, deflection: float = 1.0, do_mirror: bool = False, do_plot: bool = False, do_test: bool = False, run_to_completion: bool = False, run_resorting: bool = False, verbose: int = 0) -> Tuple['Molecule', Dict[str, Any]]: ...
