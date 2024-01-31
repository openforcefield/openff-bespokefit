from _typeshed import Incomplete
from enum import Enum
from pydantic import BaseModel, constr as constr
from qcelemental.models import Molecule as Molecule
from qcelemental.models.results import AtomicResult, AtomicResultProtocols as SinglepointProtocols, WavefunctionProperties
from qcportal.compression import CompressionEnum as CompressionEnum, decompress as decompress
from qcportal.record_models import BaseRecord as BaseRecord, RecordAddBodyBase as RecordAddBodyBase, RecordQueryFilters as RecordQueryFilters, RecordStatusEnum as RecordStatusEnum
from typing import Any, Dict, List, Optional, Union
from typing_extensions import Literal

class SinglepointDriver(str, Enum):
    energy: str
    gradient: str
    hessian: str
    properties: str
    deferred: str

class QCSpecification(BaseModel):
    class Config:
        extra: Incomplete
    program: None
    driver: SinglepointDriver
    method: None
    basis: Optional[None]
    keywords: Dict[str, Any]
    protocols: SinglepointProtocols

class Wavefunction(BaseModel):
    class Config:
        extra: Incomplete
    compression_type: CompressionEnum
    data_url_: Optional[str]
    compressed_data_: Optional[bytes]
    decompressed_data_: Optional[WavefunctionProperties]
    def propagate_client(self, client, record_base_url) -> None: ...
    @property
    def data(self) -> WavefunctionProperties: ...

class SinglepointRecord(BaseRecord):
    record_type: Literal['singlepoint']
    specification: QCSpecification
    molecule_id: int
    molecule_: Optional[Molecule]
    wavefunction_: Optional[Wavefunction]
    def propagate_client(self, client) -> None: ...
    @property
    def return_result(self) -> Any: ...
    @property
    def molecule(self) -> Molecule: ...
    @property
    def wavefunction(self) -> Optional[WavefunctionProperties]: ...
    def to_qcschema_result(self) -> AtomicResult: ...

class SinglepointAddBody(RecordAddBodyBase):
    specification: QCSpecification
    molecules: List[Union[int, Molecule]]

class SinglepointQueryFilters(RecordQueryFilters):
    program: Optional[List[None]]
    driver: Optional[List[SinglepointDriver]]
    method: Optional[List[None]]
    basis: Optional[List[Optional[None]]]
    molecule_id: Optional[List[int]]
    keywords: Optional[List[Dict[str, Any]]]
