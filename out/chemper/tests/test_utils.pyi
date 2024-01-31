from _typeshed import Incomplete
from chemper import chemper_utils as chemper_utils
from chemper.mol_toolkits import mol_toolkit as mol_toolkit

smirks_checks: Incomplete

def test_smirks_validity(smirks, is_valid) -> None: ...

chemper_data: Incomplete

def test_valid_files(fn) -> None: ...
def test_failing_files() -> None: ...

smirks1: Incomplete
smirks2: Incomplete
smirks3: Incomplete
smirks_match_sets: Incomplete

def test_matching_smirks(smirks1, smirks2, checks) -> None: ...

d1: Incomplete
d2: Incomplete
d3: Incomplete
pairs: Incomplete

def test_match_reference(cur, ref, matches, checks) -> None: ...
