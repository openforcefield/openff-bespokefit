from ..exceptions import ValidationError as ValidationError
from .regex import DECIMAL as DECIMAL
from _typeshed import Incomplete

class PubChemObj:
    url: str
    cid: Incomplete
    mf: Incomplete
    iupac: Incomplete
    molecular_charge: Incomplete
    natom: int
    dataSDF: str
    def __init__(self, cid, mf, iupac, charge) -> None: ...
    def get_sdf(self): ...
    def name(self): ...
    def get_cartesian(self): ...
    def get_molecule_string(self): ...

def get_pubchem_results(name): ...