from ..optimization.record_models import OptimizationRecord as OptimizationRecord, OptimizationSpecification as OptimizationSpecification
from ..singlepoint.record_models import QCSpecification as QCSpecification, SinglepointRecord as SinglepointRecord
from _typeshed import Incomplete
from pydantic import BaseModel, constr as constr
from qcportal.molecules import Molecule as Molecule
from qcportal.record_models import BaseRecord as BaseRecord, RecordAddBodyBase as RecordAddBodyBase, RecordQueryFilters as RecordQueryFilters
from qcportal.utils import recursive_normalizer as recursive_normalizer
from typing import Dict, List, Optional, Union
from typing_extensions import Literal

class NEBKeywords(BaseModel):
    class Config:
        extra: Incomplete
    images: int
    spring_constant: float
    spring_type: int
    maximum_force: float
    average_force: float
    maximum_cycle: int
    optimize_ts: bool
    optimize_endpoints: bool
    epsilon: float
    hessian_reset: bool
    def normalize(cls, values): ...

class NEBSpecification(BaseModel):
    class Config:
        extra: Incomplete
    program: None
    singlepoint_specification: QCSpecification
    optimization_specification: Optional[OptimizationSpecification]
    keywords: NEBKeywords

class NEBOptimization(BaseModel):
    class config:
        extra: Incomplete
    optimization_id: int
    position: int
    ts: bool

class NEBSinglepoint(BaseModel):
    class Config:
        extra: Incomplete
    singlepoint_id: int
    chain_iteration: int
    position: int

class NEBAddBody(RecordAddBodyBase):
    specification: NEBSpecification
    initial_chains: List[List[Union[int, Molecule]]]

class NEBQueryFilters(RecordQueryFilters):
    program: Optional[List[str]]
    qc_program: Optional[List[None]]
    qc_method: Optional[List[None]]
    qc_basis: Optional[List[Optional[None]]]
    molecule_id: Optional[List[int]]

class NEBRecord(BaseRecord):
    record_type: Literal['neb']
    specification: NEBSpecification
    initial_chain_molecule_ids_: Optional[List[int]]
    singlepoints_: Optional[List[NEBSinglepoint]]
    optimizations_: Optional[Dict[str, NEBOptimization]]
    initial_chain_: Optional[List[Molecule]]
    optimizations_cache_: Optional[Dict[str, OptimizationRecord]]
    singlepoints_cache_: Optional[Dict[int, List[SinglepointRecord]]]
    def propagate_client(self, client) -> None: ...
    @property
    def initial_chain(self) -> List[Molecule]: ...
    @property
    def singlepoints(self) -> Dict[int, List[SinglepointRecord]]: ...
    @property
    def neb_result(self): ...
    @property
    def optimizations(self) -> Optional[Dict[str, OptimizationRecord]]: ...
    @property
    def ts_optimization(self) -> Optional[OptimizationRecord]: ...
