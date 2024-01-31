from _typeshed import Incomplete
from enum import Enum
from pydantic import BaseModel, constr as constr
from qcportal.molecules import Molecule as Molecule
from qcportal.optimization.record_models import OptimizationRecord as OptimizationRecord, OptimizationSpecification as OptimizationSpecification
from qcportal.record_models import BaseRecord as BaseRecord, RecordAddBodyBase as RecordAddBodyBase, RecordQueryFilters as RecordQueryFilters
from qcportal.utils import recursive_normalizer as recursive_normalizer
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from typing_extensions import Literal

def serialize_key(key: Union[str, Sequence[int]]) -> str: ...
def deserialize_key(key: str) -> Union[str, Tuple[int, ...]]: ...

class ScanTypeEnum(str, Enum):
    distance: str
    angle: str
    dihedral: str

class StepTypeEnum(str, Enum):
    absolute: str
    relative: str

class ScanDimension(BaseModel):
    class Config:
        extra: Incomplete
    type: ScanTypeEnum
    indices: List[int]
    steps: List[float]
    step_type: StepTypeEnum
    def check_lower_type_step_type(cls, v): ...
    def check_indices(cls, v, values, **kwargs): ...
    def check_steps(cls, v): ...

class GridoptimizationKeywords(BaseModel):
    class Config:
        extra: Incomplete
    scans: List[ScanDimension]
    preoptimization: bool

class GridoptimizationSpecification(BaseModel):
    class Config:
        extra: Incomplete
    program: None
    optimization_specification: OptimizationSpecification
    keywords: GridoptimizationKeywords

class GridoptimizationAddBody(RecordAddBodyBase):
    specification: GridoptimizationSpecification
    initial_molecules: List[Union[int, Molecule]]

class GridoptimizationQueryFilters(RecordQueryFilters):
    program: Optional[List[str]]
    optimization_program: Optional[List[str]]
    qc_program: Optional[List[None]]
    qc_method: Optional[List[None]]
    qc_basis: Optional[List[Optional[None]]]
    initial_molecule_id: Optional[List[int]]

class GridoptimizationOptimization(BaseModel):
    class Config:
        extra: Incomplete
    optimization_id: int
    key: str
    energy: Optional[float]

class GridoptimizationRecord(BaseRecord):
    record_type: Literal['gridoptimization']
    specification: GridoptimizationSpecification
    starting_grid: Optional[List[int]]
    initial_molecule_id: int
    starting_molecule_id: Optional[int]
    initial_molecule_: Optional[Molecule]
    starting_molecule_: Optional[Molecule]
    optimizations_: Optional[List[GridoptimizationOptimization]]
    optimizations_cache_: Optional[Dict[Any, OptimizationRecord]]
    def propagate_client(self, client) -> None: ...
    @property
    def initial_molecule(self) -> Molecule: ...
    @property
    def starting_molecule(self) -> Optional[Molecule]: ...
    @property
    def optimizations(self) -> Dict[Any, OptimizationRecord]: ...
    @property
    def preoptimization(self) -> Optional[OptimizationRecord]: ...
    @property
    def final_energies(self) -> Dict[Tuple[int, ...], float]: ...
