from .datum import Datum as Datum, print_variables as print_variables
from .exceptions import DataUnavailableError as DataUnavailableError
from .periodic_table import periodictable as periodictable
from _typeshed import Incomplete
from typing import Union

class VanderWaalsRadii:
    vdwr: Incomplete
    doi: Incomplete
    native_units: Incomplete
    name: Incomplete
    year: Incomplete
    def __init__(self, context: str = 'MANTINA2009') -> None: ...
    def get(self, atom: Union[int, str], *, return_tuple: bool = False, units: str = 'bohr', missing: float = None) -> Union[float, 'Datum']: ...
    def string_representation(self) -> str: ...
    def write_c_header(self, filename: str = 'vdwrad.h', missing: float = 2.0) -> None: ...

vdwradii: Incomplete