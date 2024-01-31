from _typeshed import Incomplete
from enum import Enum
from pydantic import BaseModel, constr as constr
from qcportal.molecules import Molecule as Molecule
from qcportal.record_models import BaseRecord as BaseRecord, RecordAddBodyBase as RecordAddBodyBase, RecordQueryFilters as RecordQueryFilters
from qcportal.singlepoint.record_models import QCSpecification as QCSpecification, SinglepointRecord as SinglepointRecord
from typing import Any, Dict, List, Optional, Union
from typing_extensions import Literal

class BSSECorrectionEnum(str, Enum):
    none: str
    cp: str

class ManybodyKeywords(BaseModel):
    class Config:
        extra: Incomplete
    max_nbody: Optional[int]
    bsse_correction: BSSECorrectionEnum
    def check_max_nbody(cls, v): ...

class ManybodySpecification(BaseModel):
    class Config:
        extra: Incomplete
    program: None
    singlepoint_specification: QCSpecification
    keywords: ManybodyKeywords

class ManybodyAddBody(RecordAddBodyBase):
    specification: ManybodySpecification
    initial_molecules: List[Union[int, Molecule]]

class ManybodyQueryFilters(RecordQueryFilters):
    program: Optional[List[str]]
    qc_program: Optional[List[None]]
    qc_method: Optional[List[None]]
    qc_basis: Optional[List[Optional[None]]]
    initial_molecule_id: Optional[List[int]]

class ManybodyCluster(BaseModel):
    class Config:
        extra: Incomplete
    molecule_id: int
    fragments: List[int]
    basis: List[int]
    degeneracy: int
    singlepoint_id: Optional[int]
    molecule: Optional[Molecule]
    singlepoint_record: Optional[SinglepointRecord]

class ManybodyRecord(BaseRecord):
    record_type: Literal['manybody']
    specification: ManybodySpecification
    results: Optional[Dict[str, Any]]
    initial_molecule_id: int
    initial_molecule_: Optional[Molecule]
    clusters_: Optional[List[ManybodyCluster]]
    def propagate_client(self, client) -> None: ...
    @property
    def initial_molecule(self) -> Molecule: ...
    @property
    def clusters(self) -> List[ManybodyCluster]: ...
