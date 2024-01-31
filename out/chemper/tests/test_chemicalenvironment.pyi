from _typeshed import Incomplete
from chemper.chemper_utils import is_valid_smirks as is_valid_smirks
from chemper.graphs.environment import ChemicalEnvironment as ChemicalEnvironment
from functools import partial as partial

input_SMIRKS: Incomplete

def test_create_environments(smirks, frag_type) -> None: ...
def test_complicated_torsion() -> None: ...

selections: Incomplete

def test_selection_by_descriptor(descriptor, is_none) -> None: ...

comp_dict: Incomplete
comp_list: Incomplete

def test_get_component_list(comp, option, expected_len) -> None: ...
def test_other_env_methods() -> None: ...
def test_wrong_smirks_error() -> None: ...

decs: Incomplete

def test_ring_parsing(decorator) -> None: ...
