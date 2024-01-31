from ..exceptions import NotAnElementError as NotAnElementError, ValidationError as ValidationError
from ..periodic_table import periodictable as periodictable
from .regex import NUCLEUS as NUCLEUS
from typing import Tuple

def reconcile_nucleus(A: int = None, Z: int = None, E: str = None, mass: float = None, real: bool = None, label: str = None, speclabel: bool = True, nonphysical: bool = False, mtol: float = 0.001, verbose: int = 1) -> Tuple[int, int, str, float, bool, str]: ...
def parse_nucleus_label(label: str): ...
