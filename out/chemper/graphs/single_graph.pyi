from _typeshed import Incomplete
from chemper.mol_toolkits import mol_toolkit as mol_toolkit

class SingleGraph:
    class AtomStorage:
        atom: Incomplete
        atomic_number: Incomplete
        aromatic: Incomplete
        charge: Incomplete
        hydrogen_count: Incomplete
        connectivity: Incomplete
        ring_connectivity: Incomplete
        min_ring_size: Incomplete
        atom_index: Incomplete
        label: Incomplete
        def __init__(self, atom: Incomplete | None = None, label: Incomplete | None = None) -> None: ...
        def __lt__(self, other): ...
        def __eq__(self, other): ...
        def __hash__(self): ...
        def as_smirks(self, compress: bool = False): ...
    class BondStorage:
        order: Incomplete
        ring: Incomplete
        bond_index: Incomplete
        label: Incomplete
        def __init__(self, bond: Incomplete | None = None, label: Incomplete | None = None) -> None: ...
        def __lt__(self, other): ...
        def __eq__(self, other): ...
        def __hash__(self): ...
        def as_smirks(self): ...
    atom_by_label: Incomplete
    bond_by_label: Incomplete
    atom_by_index: Incomplete
    mol: Incomplete
    def __init__(self, mol: Incomplete | None = None, smirks_atoms: Incomplete | None = None, layers: int = 0) -> None: ...
    def __lt__(self, other): ...
    def __eq__(self, other): ...
    def __hash__(self): ...
    def as_smirks(self, compress: bool = False): ...
    def get_atoms(self): ...
    def get_connecting_bond(self, atom1, atom2): ...
    def get_bonds(self): ...
    def get_neighbors(self, atom): ...
    def remove_atom(self, atom): ...
    def add_atom(self, new_atom, new_bond: Incomplete | None = None, bond_to_atom: Incomplete | None = None, new_label: Incomplete | None = None, new_bond_label: Incomplete | None = None): ...