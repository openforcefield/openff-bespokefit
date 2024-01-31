from _typeshed import Incomplete
from pydantic import BaseModel
from qcportal.dataset_models import BaseDataset as BaseDataset
from qcportal.metadata_models import InsertMetadata as InsertMetadata
from qcportal.molecules import Molecule as Molecule
from qcportal.singlepoint.record_models import QCSpecification as QCSpecification, SinglepointRecord as SinglepointRecord
from typing import Any, Dict, Iterable, Optional, Union
from typing_extensions import Literal

class SinglepointDatasetNewEntry(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    molecule: Union[Molecule, int]
    additional_keywords: Dict[str, Any]
    attributes: Dict[str, Any]
    comment: Optional[str]
    local_results: Optional[Dict[str, Any]]

class SinglepointDatasetEntry(SinglepointDatasetNewEntry):
    molecule: Molecule

class SinglepointDatasetSpecification(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    specification: QCSpecification
    description: Optional[str]

class SinglepointDatasetRecordItem(BaseModel):
    class Config:
        extra: Incomplete
    entry_name: str
    specification_name: str
    record_id: int
    record: Optional[SinglepointRecord]

class SinglepointDataset(BaseDataset):
    dataset_type: Literal['singlepoint']
    def add_specification(self, name: str, specification: QCSpecification, description: Optional[str] = None) -> InsertMetadata: ...
    def add_entries(self, entries: Union[SinglepointDatasetNewEntry, Iterable[SinglepointDatasetNewEntry]]) -> InsertMetadata: ...
    def add_entry(self, name: str, molecule: Union[Molecule, int], additional_keywords: Optional[Dict[str, Any]] = None, attributes: Optional[Dict[str, Any]] = None, comment: Optional[str] = None): ...
