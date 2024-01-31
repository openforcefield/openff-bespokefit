from ..optimization.record_models import OptimizationRecord as OptimizationRecord, OptimizationSpecification as OptimizationSpecification
from ..singlepoint.record_models import QCSpecification as QCSpecification, SinglepointRecord as SinglepointRecord
from _typeshed import Incomplete
from pydantic import BaseModel, constr as constr
from qcportal.molecules import Molecule as Molecule
from qcportal.record_models import BaseRecord as BaseRecord, RecordAddBodyBase as RecordAddBodyBase, RecordQueryFilters as RecordQueryFilters
from typing import List, Optional, Tuple, Union
from typing_extensions import Literal

class ReactionKeywords(BaseModel):
    class Config: ...

class ReactionSpecification(BaseModel):
    class Config:
        extra: Incomplete
    program: None
    singlepoint_specification: Optional[QCSpecification]
    optimization_specification: Optional[OptimizationSpecification]
    keywords: ReactionKeywords
    def required_spec(cls, v): ...

class ReactionAddBody(RecordAddBodyBase):
    specification: ReactionSpecification
    stoichiometries: List[List[Tuple[float, Union[int, Molecule]]]]

class ReactionQueryFilters(RecordQueryFilters):
    program: Optional[List[str]]
    qc_program: Optional[List[None]]
    qc_method: Optional[List[None]]
    qc_basis: Optional[List[Optional[None]]]
    optimization_program: Optional[List[None]]
    molecule_id: Optional[List[int]]

class ReactionComponent(BaseModel):
    class Config:
        extra: Incomplete
    molecule_id: int
    coefficient: float
    singlepoint_id: Optional[int]
    optimization_id: Optional[int]
    molecule: Optional[Molecule]
    singlepoint_record: Optional[SinglepointRecord]
    optimization_record: Optional[OptimizationRecord]

class ReactionRecord(BaseRecord):
    record_type: Literal['reaction']
    specification: ReactionSpecification
    total_energy: Optional[float]
    components_: Optional[List[ReactionComponent]]
    def propagate_client(self, client) -> None: ...
    @property
    def components(self) -> List[ReactionComponent]: ...
