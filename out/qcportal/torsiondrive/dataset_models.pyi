from _typeshed import Incomplete
from pydantic import BaseModel
from qcportal.dataset_models import BaseDataset as BaseDataset
from qcportal.metadata_models import InsertMetadata as InsertMetadata
from qcportal.molecules import Molecule as Molecule
from qcportal.torsiondrive.record_models import TorsiondriveRecord as TorsiondriveRecord, TorsiondriveSpecification as TorsiondriveSpecification
from typing import Any, Dict, Iterable, List, Optional, Union
from typing_extensions import Literal

class TorsiondriveDatasetNewEntry(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    initial_molecules: List[Union[Molecule, int]]
    additional_keywords: Dict[str, Any]
    additional_optimization_keywords: Dict[str, Any]
    attributes: Dict[str, Any]
    comment: Optional[str]

class TorsiondriveDatasetEntry(TorsiondriveDatasetNewEntry):
    initial_molecules: List[Molecule]

class TorsiondriveDatasetSpecification(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    specification: TorsiondriveSpecification
    description: Optional[str]

class TorsiondriveDatasetRecordItem(BaseModel):
    class Config:
        extra: Incomplete
    entry_name: str
    specification_name: str
    record_id: int
    record: Optional[TorsiondriveRecord]

class TorsiondriveDataset(BaseDataset):
    dataset_type: Literal['torsiondrive']
    def add_specification(self, name: str, specification: TorsiondriveSpecification, description: Optional[str] = None) -> InsertMetadata: ...
    def add_entries(self, entries: Union[TorsiondriveDatasetNewEntry, Iterable[TorsiondriveDatasetNewEntry]]) -> InsertMetadata: ...
    def add_entry(self, name: str, initial_molecules: List[Union[Molecule, int]], additional_keywords: Optional[Dict[str, Any]] = None, additional_optimization_keywords: Optional[Dict[str, Any]] = None, attributes: Optional[Dict[str, Any]] = None, comment: Optional[str] = None): ...
