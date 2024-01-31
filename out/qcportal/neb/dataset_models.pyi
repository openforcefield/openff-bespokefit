from _typeshed import Incomplete
from pydantic import BaseModel
from qcportal.dataset_models import BaseDataset as BaseDataset
from qcportal.metadata_models import InsertMetadata as InsertMetadata
from qcportal.molecules import Molecule as Molecule
from qcportal.neb.record_models import NEBRecord as NEBRecord, NEBSpecification as NEBSpecification
from typing import Any, Dict, Iterable, List, Optional, Union
from typing_extensions import Literal

class NEBDatasetNewEntry(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    initial_chain: List[Union[int, Molecule]]
    additional_keywords: Dict[str, Any]
    additional_singlepoint_keywords: Dict[str, Any]
    attributes: Dict[str, Any]
    comment: Optional[str]

class NEBDatasetEntry(NEBDatasetNewEntry):
    initial_chain: List[Molecule]

class NEBDatasetSpecification(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    specification: NEBSpecification
    description: Optional[str]

class NEBDatasetRecordItem(BaseModel):
    class Config:
        extra: Incomplete
    entry_name: str
    specification_name: str
    record_id: int
    record: Optional[NEBRecord]

class NEBDataset(BaseDataset):
    dataset_type: Literal['neb']
    def add_specification(self, name: str, specification: NEBSpecification, description: Optional[str] = None) -> InsertMetadata: ...
    def add_entries(self, entries: Union[NEBDatasetNewEntry, Iterable[NEBDatasetNewEntry]]) -> InsertMetadata: ...
    def add_entry(self, name: str, initial_chain: List[Union[Molecule, int]], additional_keywords: Optional[Dict[str, Any]] = None, additional_singlepoint_keywords: Optional[Dict[str, Any]] = None, attributes: Optional[Dict[str, Any]] = None, comment: Optional[str] = None): ...
