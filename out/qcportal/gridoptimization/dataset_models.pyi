from _typeshed import Incomplete
from pydantic import BaseModel
from qcportal.dataset_models import BaseDataset as BaseDataset
from qcportal.gridoptimization.record_models import GridoptimizationRecord as GridoptimizationRecord, GridoptimizationSpecification as GridoptimizationSpecification
from qcportal.metadata_models import InsertMetadata as InsertMetadata
from qcportal.molecules import Molecule as Molecule
from typing import Any, Dict, Iterable, Optional, Union
from typing_extensions import Literal

class GridoptimizationDatasetNewEntry(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    initial_molecule: Union[Molecule, int]
    additional_keywords: Dict[str, Any]
    additional_optimization_keywords: Dict[str, Any]
    attributes: Dict[str, Any]
    comment: Optional[str]

class GridoptimizationDatasetEntry(GridoptimizationDatasetNewEntry):
    initial_molecule: Molecule

class GridoptimizationDatasetSpecification(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    specification: GridoptimizationSpecification
    description: Optional[str]

class GridoptimizationDatasetRecordItem(BaseModel):
    class Config:
        extra: Incomplete
    entry_name: str
    specification_name: str
    record_id: int
    record: Optional[GridoptimizationRecord]

class GridoptimizationDataset(BaseDataset):
    dataset_type: Literal['gridoptimization']
    def add_specification(self, name: str, specification: GridoptimizationSpecification, description: Optional[str] = None) -> InsertMetadata: ...
    def add_entries(self, entries: Union[GridoptimizationDatasetNewEntry, Iterable[GridoptimizationDatasetNewEntry]]) -> InsertMetadata: ...
    def add_entry(self, name: str, initial_molecule: Union[Molecule, int], additional_keywords: Optional[Dict[str, Any]] = None, additional_optimization_keywords: Optional[Dict[str, Any]] = None, attributes: Optional[Dict[str, Any]] = None, comment: Optional[str] = None): ...
