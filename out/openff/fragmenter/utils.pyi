from openff.toolkit.topology import Molecule as Molecule
from openff.toolkit.utils import ToolkitRegistry, ToolkitWrapper
from typing import Dict, Union

def default_functional_groups() -> Dict[str, str]: ...
def get_map_index(molecule: Molecule, atom_index: int, error_on_missing: bool = True) -> int: ...
def get_atom_index(molecule: Molecule, map_index: int) -> int: ...
def global_toolkit_registry(toolkit_registry: Union[ToolkitRegistry, ToolkitWrapper]): ...