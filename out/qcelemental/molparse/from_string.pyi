from typing import Dict, Tuple, Union

__all__ = ['from_string']

def from_string(molstr: str, dtype: str = None, *, name: str = None, fix_com: bool = None, fix_orientation: bool = None, fix_symmetry: str = None, return_processed: bool = False, enable_qm: bool = True, enable_efp: bool = True, missing_enabled_return_qm: str = 'none', missing_enabled_return_efp: str = 'none', verbose: int = 1) -> Union[Dict, Tuple[Dict, Dict]]: ...
