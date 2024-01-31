import numpy as np
from ..exceptions import ValidationError as ValidationError
from ..util import provenance_stamp as provenance_stamp
from .from_arrays import from_arrays as from_arrays
from typing import Dict, List, Union

def from_schema(molschema: Dict, *, nonphysical: bool = False, verbose: int = 1) -> Dict: ...
def contiguize_from_fragment_pattern(frag_pattern: List[List[int]], *, geom: Union[np.ndarray, List[List]] = None, verbose: int = 1, throw_reorder: bool = False, **kwargs): ...
