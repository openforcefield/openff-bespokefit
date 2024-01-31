from ..exceptions import ValidationError as ValidationError
from ..physical_constants import constants as constants
from ..util import unnp as unnp
from .to_string import formula_generator as formula_generator
from typing import Any, Dict, Union

def to_schema(molrec: Dict[str, Any], dtype: Union[str, int], units: str = 'Bohr', *, np_out: bool = False, copy: bool = True) -> Dict[str, Any]: ...
