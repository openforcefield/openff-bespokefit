from _typeshed import Incomplete
from pydantic import BaseModel
from qcportal.dataset_models import BaseDataset as BaseDataset
from qcportal.metadata_models import InsertMetadata as InsertMetadata
from qcportal.molecules import Molecule as Molecule
from qcportal.optimization.record_models import OptimizationRecord as OptimizationRecord, OptimizationSpecification as OptimizationSpecification
from typing import Any, Dict, Iterable, Optional, Union
from typing_extensions import Literal

class OptimizationDatasetNewEntry(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    initial_molecule: Union[Molecule, int]
    additional_keywords: Dict[str, Any]
    attributes: Dict[str, Any]
    comment: Optional[str]

class OptimizationDatasetEntry(OptimizationDatasetNewEntry):
    initial_molecule: Molecule

class OptimizationDatasetSpecification(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    specification: OptimizationSpecification
    description: Optional[str]

class OptimizationDatasetRecordItem(BaseModel):
    class Config:
        extra: Incomplete
    entry_name: str
    specification_name: str
    record_id: int
    record: Optional[OptimizationRecord]

class OptimizationDataset(BaseDataset):
    dataset_type: Literal['optimization']
    def add_specification(self, name: str, specification: OptimizationSpecification, description: Optional[str] = None) -> InsertMetadata: ...
    def add_entries(self, entries: Union[OptimizationDatasetNewEntry, Iterable[OptimizationDatasetNewEntry]]) -> InsertMetadata: ...
    def add_entry(self, name: str, initial_molecule: Union[Molecule, int], additional_keywords: Optional[Dict[str, Any]] = None, attributes: Optional[Dict[str, Any]] = None, comment: Optional[str] = None): ...
