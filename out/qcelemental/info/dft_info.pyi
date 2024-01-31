from ..models import ProtoModel as ProtoModel
from _typeshed import Incomplete

class DFTFunctionalInfo(ProtoModel):
    name: str
    ansatz: int
    deriv: int
    c_hybrid: bool
    x_hybrid: bool
    c_lrc: bool
    x_lrc: bool
    nlc: bool

class DFTFunctionalContext:
    suffixes: Incomplete
    functionals: Incomplete
    name: Incomplete
    def __init__(self, context: str = 'defualt') -> None: ...

dftfunctionalinfo: Incomplete

def get(name: str) -> DFTFunctionalInfo: ...
