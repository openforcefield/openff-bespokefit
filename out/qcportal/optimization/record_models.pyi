from _typeshed import Incomplete
from pydantic import BaseModel, constr as constr
from qcelemental.models import Molecule as Molecule
from qcelemental.models.procedures import OptimizationProtocols, OptimizationResult
from qcportal.record_models import BaseRecord as BaseRecord, RecordAddBodyBase as RecordAddBodyBase, RecordQueryFilters as RecordQueryFilters, RecordStatusEnum as RecordStatusEnum
from qcportal.singlepoint import QCSpecification as QCSpecification, SinglepointDriver as SinglepointDriver, SinglepointProtocols as SinglepointProtocols, SinglepointRecord as SinglepointRecord
from typing import Any, Dict, List, Optional, Union
from typing_extensions import Literal

class OptimizationSpecification(BaseModel):
    class Config:
        extra: Incomplete
    program: None
    qc_specification: QCSpecification
    keywords: Dict[str, Any]
    protocols: OptimizationProtocols
    def force_qcspec(cls, v): ...

class OptimizationRecord(BaseRecord):
    record_type: Literal['optimization']
    specification: OptimizationSpecification
    initial_molecule_id: int
    final_molecule_id: Optional[int]
    energies: Optional[List[float]]
    initial_molecule_: Optional[Molecule]
    final_molecule_: Optional[Molecule]
    trajectory_ids_: Optional[List[int]]
    trajectory_records_: Optional[List[SinglepointRecord]]
    def propagate_client(self, client) -> None: ...
    @property
    def initial_molecule(self) -> Molecule: ...
    @property
    def final_molecule(self) -> Optional[Molecule]: ...
    @property
    def trajectory(self) -> Optional[List[SinglepointRecord]]: ...
    def trajectory_element(self, trajectory_index: int) -> SinglepointRecord: ...
    def to_qcschema_result(self) -> OptimizationResult: ...

class OptimizationQueryFilters(RecordQueryFilters):
    program: Optional[List[str]]
    qc_program: Optional[List[None]]
    qc_method: Optional[List[None]]
    qc_basis: Optional[List[Optional[None]]]
    initial_molecule_id: Optional[List[int]]
    final_molecule_id: Optional[List[int]]

class OptimizationAddBody(RecordAddBodyBase):
    specification: OptimizationSpecification
    initial_molecules: List[Union[int, Molecule]]
