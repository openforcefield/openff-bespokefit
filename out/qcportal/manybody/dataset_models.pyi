from _typeshed import Incomplete
from pydantic import BaseModel
from qcportal.dataset_models import BaseDataset as BaseDataset
from qcportal.manybody.record_models import ManybodyRecord as ManybodyRecord, ManybodySpecification as ManybodySpecification
from qcportal.metadata_models import InsertMetadata as InsertMetadata
from qcportal.molecules import Molecule as Molecule
from typing import Any, Dict, Iterable, Optional, Union
from typing_extensions import Literal

class ManybodyDatasetNewEntry(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    initial_molecule: Union[Molecule, int]
    additional_keywords: Dict[str, Any]
    attributes: Dict[str, Any]
    comment: Optional[str]

class ManybodyDatasetEntry(ManybodyDatasetNewEntry):
    initial_molecule: Molecule

class ManybodyDatasetSpecification(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    specification: ManybodySpecification
    description: Optional[str]

class ManybodyDatasetRecordItem(BaseModel):
    entry_name: str
    specification_name: str
    record_id: int
    record: Optional[ManybodyRecord]

class ManybodyDataset(BaseDataset):
    dataset_type: Literal['manybody']
    def add_specification(self, name: str, specification: ManybodySpecification, description: Optional[str] = None) -> InsertMetadata: ...
    def add_entries(self, entries: Union[ManybodyDatasetNewEntry, Iterable[ManybodyDatasetNewEntry]]) -> InsertMetadata: ...
    def add_entry(self, name: str, initial_molecule: Union[int, Molecule], additional_keywords: Optional[Dict[str, Any]] = None, attributes: Optional[Dict[str, Any]] = None, comment: Optional[str] = None): ...
