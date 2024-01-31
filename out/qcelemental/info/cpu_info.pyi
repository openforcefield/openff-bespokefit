from ..models import ProtoModel as ProtoModel
from _typeshed import Incomplete
from enum import Enum
from typing import Optional

class VendorEnum(str, Enum):
    amd: str
    intel: str
    nvidia: str
    arm: str

class InstructionSetEnum(int, Enum):
    none: int
    sse: int
    avx: int
    avx2: int
    avx512: int

class ProcessorInfo(ProtoModel):
    name: str
    ncores: int
    nthreads: Optional[int]
    base_clock: float
    boost_clock: Optional[float]
    model: str
    family: str
    launch_date: Optional[int]
    target_use: str
    vendor: VendorEnum
    microarchitecture: Optional[str]
    instructions: InstructionSetEnum
    type: str

class ProcessorContext:
    processors: Incomplete
    index: Incomplete
    index_vendor: Incomplete
    name: Incomplete
    def __init__(self, context: str = 'defualt') -> None: ...
    def process_names(self, name): ...

context: Incomplete

def get(name: str, vendor: Incomplete | None = None, cutoff: float = 0.9) -> ProcessorInfo: ...
def list_names(): ...
