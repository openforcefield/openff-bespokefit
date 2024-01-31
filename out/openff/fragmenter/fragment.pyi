import abc
from _typeshed import Incomplete
from openff.toolkit.topology import Atom as Atom, Molecule
from openff.toolkit.utils import ToolkitRegistry as ToolkitRegistry, ToolkitWrapper as ToolkitWrapper
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from typing_extensions import Literal

logger: Incomplete
BondTuple = Tuple[int, int]
AtomAndBondSet = Tuple[Set[int], Set[BondTuple]]
Stereochemistries = Dict[Union[int, BondTuple], str]
RingSystems = Dict[int, AtomAndBondSet]
FunctionalGroups = Dict[str, AtomAndBondSet]
Heuristic: Incomplete

class Fragment(BaseModel):
    smiles: str
    bond_indices: Tuple[int, int]
    @property
    def molecule(self) -> Molecule: ...

class FragmentationResult(BaseModel):
    parent_smiles: str
    fragments: List[Fragment]
    provenance: Dict[str, Any]
    @property
    def parent_molecule(self) -> Molecule: ...
    @property
    def fragment_molecules(self) -> Dict[BondTuple, Molecule]: ...
    @property
    def fragments_by_bond(self) -> Dict[BondTuple, Fragment]: ...

class Fragmenter(BaseModel, abc.ABC, metaclass=abc.ABCMeta):
    functional_groups: Dict[str, str]
    @classmethod
    def find_rotatable_bonds(cls, molecule: Molecule, target_bond_smarts: Optional[List[str]]) -> List[BondTuple]: ...
    def fragment(self, molecule: Molecule, target_bond_smarts: Optional[List[str]] = None, toolkit_registry: Optional[Union[ToolkitRegistry, ToolkitWrapper]] = None) -> FragmentationResult: ...

class WBOOptions(BaseModel):
    method: Literal['am1-wiberg-elf10']
    max_conformers: int
    rms_threshold: float

class WBOFragmenter(Fragmenter):
    scheme: Literal['WBO']
    wbo_options: WBOOptions
    threshold: float
    heuristic: Heuristic
    keep_non_rotor_ring_substituents: bool

class PfizerFragmenter(Fragmenter):
    scheme: Literal['Pfizer']
