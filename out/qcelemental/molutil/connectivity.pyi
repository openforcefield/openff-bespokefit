import numpy as np
from typing import List, Optional, Tuple, Union

__all__ = ['guess_connectivity']

def guess_connectivity(symbols: np.ndarray, geometry: np.ndarray, threshold: float = 1.2, default_connectivity: Optional[float] = None) -> List[Union[Tuple[int, int], Tuple[int, int, float]]]: ...
