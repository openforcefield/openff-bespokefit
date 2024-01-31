from _typeshed import Incomplete
from pydantic import BaseModel
from qcportal.dataset_models import BaseDataset as BaseDataset
from qcportal.metadata_models import InsertMetadata as InsertMetadata
from qcportal.molecules import Molecule as Molecule
from qcportal.reaction.record_models import ReactionRecord as ReactionRecord, ReactionSpecification as ReactionSpecification
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from typing_extensions import Literal

class ReactionDatasetEntryStoichiometry(BaseModel):
    coefficient: float
    molecule: Molecule

class ReactionDatasetNewEntry(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    stoichiometries: List[Union[ReactionDatasetEntryStoichiometry, Tuple[float, Union[int, Molecule]]]]
    additional_keywords: Dict[str, Any]
    attributes: Dict[str, Any]
    comment: Optional[str]

class ReactionDatasetEntry(ReactionDatasetNewEntry):
    class Config:
        extra: Incomplete
    stoichiometries: List[ReactionDatasetEntryStoichiometry]

class ReactionDatasetSpecification(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    specification: ReactionSpecification
    description: Optional[str]

class ReactionDatasetRecordItem(BaseModel):
    class Config:
        extra: Incomplete
    entry_name: str
    specification_name: str
    record_id: int
    record: Optional[ReactionRecord]

class ReactionDataset(BaseDataset):
    dataset_type: Literal['reaction']
    def add_specification(self, name: str, specification: ReactionSpecification, description: Optional[str] = None) -> InsertMetadata: ...
    def add_entries(self, entries: Union[ReactionDatasetEntry, Iterable[ReactionDatasetNewEntry]]) -> InsertMetadata: ...
    def add_entry(self, name: str, stoichiometries: List[Tuple[float, Union[int, Molecule]]], additional_keywords: Optional[Dict[str, Any]] = None, attributes: Optional[Dict[str, Any]] = None, comment: Optional[str] = None): ...
