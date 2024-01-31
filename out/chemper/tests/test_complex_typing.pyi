from _typeshed import Incomplete
from chemper.chemper_utils import create_tuples_for_clusters as create_tuples_for_clusters, get_data_path as get_data_path, get_full_path as get_full_path, get_typed_molecules as get_typed_molecules
from chemper.mol_toolkits.mol_toolkit import mols_from_mol2 as mols_from_mol2
from chemper.smirksify import SMIRKSifier as SMIRKSifier
from copy import deepcopy as deepcopy

def parse_smarts_file(smarts_file_name): ...

mol_files: Incomplete
fragments: Incomplete
pairs: Incomplete

def test_complex_clusters(mol_file, frag) -> None: ...
