import numpy as np
from ..exceptions import ValidationError as ValidationError
from ..util import unique_everseen as unique_everseen
from typing import Any, Dict, List, Union

def validate_and_fill_chgmult(zeff: np.ndarray, fragment_separators: np.ndarray, molecular_charge: Union[float, None], fragment_charges: Union[List[float], None], molecular_multiplicity: Union[int, None], fragment_multiplicities: Union[List[int], None], zero_ghost_fragments: bool = False, verbose: int = 1) -> Dict[str, Any]: ...
