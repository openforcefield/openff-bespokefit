from ..optimization.record_models import OptimizationRecord as OptimizationRecord, OptimizationSpecification as OptimizationSpecification
from _typeshed import Incomplete
from pydantic import BaseModel, constr as constr
from qcportal.molecules import Molecule as Molecule
from qcportal.record_models import BaseRecord as BaseRecord, RecordAddBodyBase as RecordAddBodyBase, RecordQueryFilters as RecordQueryFilters
from qcportal.utils import recursive_normalizer as recursive_normalizer
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from typing_extensions import Literal

def serialize_key(key: Union[str, Sequence[int]]) -> str: ...
def deserialize_key(key: str) -> Union[str, Tuple[int, ...]]: ...

class TorsiondriveKeywords(BaseModel):
    class Config:
        extra: Incomplete
    dihedrals: List[Tuple[int, int, int, int]]
    grid_spacing: List[int]
    dihedral_ranges: Optional[List[Tuple[int, int]]]
    energy_decrease_thresh: Optional[float]
    energy_upper_limit: Optional[float]
    def normalize(cls, values): ...

class TorsiondriveSpecification(BaseModel):
    class Config:
        extra: Incomplete
    program: None
    optimization_specification: OptimizationSpecification
    keywords: TorsiondriveKeywords

class TorsiondriveOptimization(BaseModel):
    class Config:
        extra: Incomplete
    optimization_id: int
    key: str
    position: int
    energy: Optional[float]

class TorsiondriveAddBody(RecordAddBodyBase):
    specification: TorsiondriveSpecification
    initial_molecules: List[List[Union[int, Molecule]]]
    as_service: bool

class TorsiondriveQueryFilters(RecordQueryFilters):
    program: Optional[List[str]]
    optimization_program: Optional[List[str]]
    qc_program: Optional[List[None]]
    qc_method: Optional[List[None]]
    qc_basis: Optional[List[Optional[None]]]
    initial_molecule_id: Optional[List[int]]

class TorsiondriveRecord(BaseRecord):
    record_type: Literal['torsiondrive']
    specification: TorsiondriveSpecification
    initial_molecules_ids_: Optional[List[int]]
    optimizations_: Optional[List[TorsiondriveOptimization]]
    initial_molecules_: Optional[List[Molecule]]
    optimizations_cache_: Optional[Dict[Any, List[OptimizationRecord]]]
    minimum_optimizations_cache_: Optional[Dict[Any, OptimizationRecord]]
    def propagate_client(self, client) -> None: ...
    @property
    def initial_molecules(self) -> List[Molecule]: ...
    @property
    def optimizations(self) -> Dict[str, List[OptimizationRecord]]: ...
    @property
    def minimum_optimizations(self) -> Dict[Tuple[float, ...], OptimizationRecord]: ...
    @property
    def final_energies(self) -> Dict[Tuple[float, ...], float]: ...
