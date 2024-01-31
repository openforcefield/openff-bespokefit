from _typeshed import Incomplete
from openff.fragmenter.fragment import BondTuple as BondTuple
from openff.toolkit.topology import Molecule as Molecule
from typing import Dict, Set, TypeVar, Union

T = TypeVar('T')
has_openeye: bool
using_openeye: Incomplete

def smarts_set_to_map_indices(input_set: Set[str], molecule: Molecule) -> Set[Union[int, BondTuple]]: ...
def key_smarts_to_map_indices(input_dictionary: Dict[str, T], molecule: Molecule) -> Dict[Union[int, BondTuple], T]: ...
def value_smarts_to_map_indices(input_dictionary: Dict[str, Set[str]], molecule: Molecule) -> Dict[str, Set[Union[int, BondTuple]]]: ...
