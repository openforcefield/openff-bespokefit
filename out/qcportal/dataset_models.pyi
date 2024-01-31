import pandas as pd
from _typeshed import Incomplete
from pydantic import BaseModel, Field as Field
from qcelemental.models.types import Array as Array
from qcportal.base_models import CommonBulkGetBody as CommonBulkGetBody, RestModelBase as RestModelBase, validate_list_to_single as validate_list_to_single
from qcportal.dataset_view import DatasetViewWrapper as DatasetViewWrapper
from qcportal.metadata_models import DeleteMetadata as DeleteMetadata, InsertMetadata as InsertMetadata
from qcportal.record_models import BaseRecord as BaseRecord, PriorityEnum as PriorityEnum, RecordStatusEnum as RecordStatusEnum
from qcportal.utils import chunk_iterable as chunk_iterable, make_list as make_list
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

class Citation(BaseModel):
    class Config:
        extra: Incomplete
        allow_mutation: bool
    acs_citation: Optional[str]
    bibtex: Optional[str]
    doi: Optional[str]
    url: Optional[str]
    def to_acs(self) -> str: ...

class ContributedValues(BaseModel):
    class Config:
        extra: Incomplete
        allow_mutation: bool
    name: str
    values: Any
    index: Array[str]
    values_structure: Dict[str, Any]
    theory_level: Union[str, Dict[str, str]]
    units: str
    theory_level_details: Optional[Union[str, Dict[str, Optional[str]]]]
    citations: Optional[List[Citation]]
    external_url: Optional[str]
    doi: Optional[str]
    comments: Optional[str]

class BaseDataset(BaseModel):
    class Config:
        extra: Incomplete
        allow_mutation: bool
        validate_assignment: bool
    id: int
    dataset_type: str
    name: str
    description: str
    tagline: str
    tags: List[str]
    group: str
    visibility: bool
    provenance: Dict[str, Any]
    default_tag: str
    default_priority: PriorityEnum
    owner_user: Optional[str]
    owner_group: Optional[str]
    metadata: Dict[str, Any]
    extras: Dict[str, Any]
    auto_fetch_missing: bool
    def __init__(self, client: Incomplete | None = None, view_data: Incomplete | None = None, **kwargs) -> None: ...
    def __init_subclass__(cls) -> None: ...
    @classmethod
    def get_subclass(cls, dataset_type: str): ...
    def propagate_client(self, client) -> None: ...
    def submit(self, entry_names: Optional[Union[str, Iterable[str]]] = None, specification_names: Optional[Union[str, Iterable[str]]] = None, tag: Optional[str] = None, priority: PriorityEnum = None, find_existing: bool = True): ...
    def status(self) -> Dict[str, Any]: ...
    def status_table(self) -> str: ...
    def print_status(self) -> None: ...
    def detailed_status(self) -> List[Tuple[str, str, RecordStatusEnum]]: ...
    @property
    def offline(self) -> bool: ...
    def assert_online(self) -> None: ...
    @property
    def record_count(self) -> int: ...
    @property
    def computed_properties(self): ...
    @property
    def is_view(self) -> bool: ...
    def assert_is_not_view(self) -> None: ...
    def set_name(self, new_name: str): ...
    def set_description(self, new_description: str): ...
    def set_visibility(self, new_visibility: bool): ...
    def set_group(self, new_group: str): ...
    def set_tags(self, new_tags: List[str]): ...
    def set_tagline(self, new_tagline: str): ...
    def set_provenance(self, new_provenance: Dict[str, Any]): ...
    def set_metadata(self, new_metadata: Dict[str, Any]): ...
    def set_default_tag(self, new_default_tag: str): ...
    def set_default_priority(self, new_default_priority: PriorityEnum): ...
    @property
    def specifications(self) -> Dict[str, Any]: ...
    @property
    def specification_names(self) -> List[str]: ...
    def fetch_specifications(self) -> None: ...
    def rename_specification(self, old_name: str, new_name: str): ...
    def delete_specification(self, name: str, delete_records: bool = False) -> DeleteMetadata: ...
    def fetch_entry_names(self) -> None: ...
    def fetch_entries(self, entry_names: Optional[Union[str, Iterable[str]]] = None, force_refetch: bool = False) -> None: ...
    def get_entry(self, entry_name: str, force_refetch: bool = False) -> Optional[Any]: ...
    def iterate_entries(self, entry_names: Optional[Union[str, Iterable[str]]] = None, force_refetch: bool = False): ...
    @property
    def entry_names(self) -> List[str]: ...
    def rename_entries(self, name_map: Dict[str, str]): ...
    def delete_entries(self, names: Union[str, Iterable[str]], delete_records: bool = False) -> DeleteMetadata: ...
    def fetch_records(self, entry_names: Optional[Union[str, Iterable[str]]] = None, specification_names: Optional[Union[str, Iterable[str]]] = None, status: Optional[Union[RecordStatusEnum, Iterable[RecordStatusEnum]]] = None, include: Optional[Iterable[str]] = None, fetch_updated: bool = True, force_refetch: bool = False): ...
    def get_record(self, entry_name: str, specification_name: str, include: Optional[Iterable[str]] = None, force_refetch: bool = False) -> Optional[BaseRecord]: ...
    def iterate_records(self, entry_names: Optional[Union[str, Iterable[str]]] = None, specification_names: Optional[Union[str, Iterable[str]]] = None, status: Optional[Union[RecordStatusEnum, Iterable[RecordStatusEnum]]] = None, include: Optional[Iterable[str]] = None, fetch_updated: bool = True, force_refetch: bool = False): ...
    def remove_records(self, entry_names: Optional[Union[str, Iterable[str]]] = None, specification_names: Optional[Union[str, Iterable[str]]] = None, delete_records: bool = False) -> DeleteMetadata: ...
    def modify_records(self, entry_names: Optional[Union[str, Iterable[str]]] = None, specification_names: Optional[Union[str, Iterable[str]]] = None, new_tag: Optional[str] = None, new_priority: Optional[PriorityEnum] = None, new_comment: Optional[str] = None, *, refetch_records: bool = False): ...
    def reset_records(self, entry_names: Optional[Union[str, Iterable[str]]] = None, specification_names: Optional[Union[str, Iterable[str]]] = None, *, refetch_records: bool = False): ...
    def cancel_records(self, entry_names: Optional[Union[str, Iterable[str]]] = None, specification_names: Optional[Union[str, Iterable[str]]] = None, *, refetch_records: bool = False): ...
    def uncancel_records(self, entry_names: Optional[Union[str, Iterable[str]]] = None, specification_names: Optional[Union[str, Iterable[str]]] = None, *, refetch_records: bool = False): ...
    def invalidate_records(self, entry_names: Optional[Union[str, Iterable[str]]] = None, specification_names: Optional[Union[str, Iterable[str]]] = None, *, refetch_records: bool = False): ...
    def uninvalidate_records(self, entry_names: Optional[Union[str, Iterable[str]]] = None, specification_names: Optional[Union[str, Iterable[str]]] = None, *, refetch_records: bool = False): ...
    def compile_values(self, value_call: Callable, value_names: Union[Sequence[str], str] = 'value', entry_names: Optional[Union[str, Iterable[str]]] = None, specification_names: Optional[Union[str, Iterable[str]]] = None, unpack: bool = False) -> pd.DataFrame: ...
    def get_properties_df(self, properties_list: Sequence[str]) -> pd.DataFrame: ...
    def fetch_contributed_values(self) -> None: ...
    @property
    def contributed_values(self) -> Dict[str, ContributedValues]: ...

class DatasetAddBody(RestModelBase):
    name: str
    description: str
    tagline: str
    tags: List[str]
    group: str
    provenance: Dict[str, Any]
    visibility: bool
    default_tag: str
    default_priority: PriorityEnum
    metadata: Dict[str, Any]
    owner_group: Optional[str]
    existing_ok: bool

class DatasetModifyMetadata(RestModelBase):
    name: str
    description: str
    tags: List[str]
    tagline: str
    group: str
    visibility: bool
    provenance: Optional[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]]
    default_tag: str
    default_priority: PriorityEnum

class DatasetQueryModel(RestModelBase):
    dataset_type: Optional[str]
    dataset_name: Optional[str]
    include: Optional[List[str]]
    exclude: Optional[List[str]]

class DatasetFetchSpecificationBody(RestModelBase):
    names: List[str]
    missing_ok: bool

class DatasetFetchEntryBody(RestModelBase):
    names: List[str]
    missing_ok: bool

class DatasetDeleteStrBody(RestModelBase):
    names: List[str]
    delete_records: bool

class DatasetRemoveRecordsBody(RestModelBase):
    entry_names: List[str]
    specification_names: List[str]
    delete_records: bool

class DatasetDeleteParams(RestModelBase):
    delete_records: bool
    def validate_lists(cls, v): ...

class DatasetFetchRecordsBody(RestModelBase):
    entry_names: List[str]
    specification_names: List[str]
    status: Optional[List[RecordStatusEnum]]

class DatasetSubmitBody(RestModelBase):
    entry_names: Optional[List[str]]
    specification_names: Optional[List[str]]
    tag: Optional[str]
    priority: Optional[PriorityEnum]
    owner_group: Optional[str]
    find_existing: bool

class DatasetRecordModifyBody(RestModelBase):
    entry_names: Optional[List[str]]
    specification_names: Optional[List[str]]
    status: Optional[RecordStatusEnum]
    priority: Optional[PriorityEnum]
    tag: Optional[str]
    comment: Optional[str]

class DatasetRecordRevertBody(RestModelBase):
    entry_names: Optional[List[str]]
    specification_names: Optional[List[str]]
    revert_status: RecordStatusEnum

class DatasetQueryRecords(RestModelBase):
    record_id: List[int]
    dataset_type: Optional[List[str]]

class DatasetDeleteEntryBody(RestModelBase):
    names: List[str]
    delete_records: bool

class DatasetDeleteSpecificationBody(RestModelBase):
    names: List[str]
    delete_records: bool

def dataset_from_dict(data: Dict[str, Any], client: Any, view_data: Optional[DatasetViewWrapper] = None) -> BaseDataset: ...
def load_dataset_view(view_path: str): ...
