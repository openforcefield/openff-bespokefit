from ..datum import Datum as Datum, print_variables as print_variables
from .ureg import build_units_registry as build_units_registry
from _typeshed import Incomplete
from pint import Quantity as _Quantity, UnitRegistry as UnitRegistry
from typing import Union

class PhysicalConstantsContext:
    h: float
    c: float
    kb: float
    R: float
    bohr2angstroms: float
    bohr2cm: float
    amu2g: float
    amu2kg: float
    hartree2J: float
    hartree2aJ: float
    cal2J: float
    dipmom_au2si: float
    dipmom_au2debye: float
    c_au: float
    hartree2ev: float
    hartree2wavenumbers: float
    hartree2kcalmol: float
    hartree2kJmol: float
    hartree2MHz: float
    kcalmol2wavenumbers: float
    e0: float
    na: float
    me: float
    pc: Incomplete
    doi: Incomplete
    raw_codata: Incomplete
    name: Incomplete
    year: Incomplete
    def __init__(self, context: str = 'CODATA2014') -> None: ...
    @property
    def ureg(self) -> UnitRegistry: ...
    def get(self, physical_constant: str, return_tuple: bool = False) -> Union[float, Datum]: ...
    def Quantity(self, data: str) -> _Quantity: ...
    def conversion_factor(self, base_unit: Union[str, '_Quantity'], conv_unit: Union[str, '_Quantity']) -> float: ...
    def string_representation(self) -> str: ...

def run_comparison(context: str) -> None: ...
def run_internal_comparison(old_context: str, new_context: str) -> None: ...
def write_c_header(context, filename: str = 'physconst.h', prefix: str = 'pc_') -> None: ...
def write_fortran_header(context, filename: str = 'physconst.fh', prefix: str = 'pc_', kind: Incomplete | None = None) -> None: ...

constants: Incomplete
