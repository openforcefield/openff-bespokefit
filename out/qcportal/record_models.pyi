from _typeshed import Incomplete
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, constr as constr
from qcelemental.models.results import Provenance as Provenance
from qcportal.base_models import QueryIteratorBase as QueryIteratorBase, QueryModelBase as QueryModelBase, RestModelBase as RestModelBase
from qcportal.compression import CompressionEnum as CompressionEnum, decompress as decompress, get_compressed_ext as get_compressed_ext
from typing import Any, Dict, Iterable, List, Optional, Sequence, Type, Union

class PriorityEnum(int, Enum):
    high: int
    normal: int
    low: int

class RecordStatusEnum(str, Enum):
    complete: str
    invalid: str
    running: str
    error: str
    waiting: str
    cancelled: str
    deleted: str
    @classmethod
    def make_ordered_status(cls, statuses: Iterable[RecordStatusEnum]) -> List[RecordStatusEnum]: ...

class OutputTypeEnum(str, Enum):
    stdout: str
    stderr: str
    error: str

class OutputStore(BaseModel):
    class Config:
        extra: Incomplete
    output_type: OutputTypeEnum
    compression_type: CompressionEnum
    data_url_: Optional[str]
    compressed_data_: Optional[bytes]
    decompressed_data_: Optional[Any]
    def propagate_client(self, client, history_base_url) -> None: ...
    @property
    def data(self) -> Any: ...

class ComputeHistory(BaseModel):
    class Config:
        extra: Incomplete
    id: int
    record_id: int
    status: RecordStatusEnum
    manager_name: Optional[str]
    modified_on: datetime
    provenance: Optional[Provenance]
    outputs_: Optional[Dict[str, OutputStore]]
    def propagate_client(self, client, record_base_url) -> None: ...
    @property
    def outputs(self) -> Dict[str, OutputStore]: ...
    def get_output(self, output_type: OutputTypeEnum) -> Any: ...
    @property
    def stdout(self) -> Any: ...
    @property
    def stderr(self) -> Any: ...
    @property
    def error(self) -> Any: ...

class NativeFile(BaseModel):
    class Config:
        extra: Incomplete
    name: str
    compression_type: CompressionEnum
    data_url_: Optional[str]
    compressed_data_: Optional[bytes]
    decompressed_data_: Optional[Any]
    def propagate_client(self, client, record_base_url) -> None: ...
    @property
    def data(self) -> Any: ...
    def save_file(self, directory: str, new_name: Optional[str] = None, keep_compressed: bool = False, overwrite: bool = False): ...

class RecordInfoBackup(BaseModel):
    class Config:
        extra: Incomplete
    old_status: RecordStatusEnum
    old_tag: Optional[str]
    old_priority: Optional[PriorityEnum]
    modified_on: datetime

class RecordComment(BaseModel):
    class Config:
        extra: Incomplete
    id: int
    record_id: int
    username: Optional[str]
    timestamp: datetime
    comment: str

class RecordTask(BaseModel):
    class Config:
        extra: Incomplete
    id: int
    record_id: int
    function: Optional[str]
    function_kwargs_compressed: Optional[bytes]
    tag: str
    priority: PriorityEnum
    required_programs: List[str]
    @property
    def function_kwargs(self) -> Optional[Dict[str, Any]]: ...

class ServiceDependency(BaseModel):
    class Config:
        extra: Incomplete
    record_id: int
    extras: Dict[str, Any]

class RecordService(BaseModel):
    class Config:
        extra: Incomplete
    id: int
    record_id: int
    tag: str
    priority: PriorityEnum
    find_existing: bool
    service_state: Optional[Dict[str, Any]]
    dependencies: List[ServiceDependency]

class BaseRecord(BaseModel):
    class Config:
        extra: Incomplete
        allow_mutation: bool
        validate_assignment: bool
    id: int
    record_type: str
    is_service: bool
    properties: Optional[Dict[str, Any]]
    extras: Optional[Dict[str, Any]]
    status: RecordStatusEnum
    manager_name: Optional[str]
    created_on: datetime
    modified_on: datetime
    owner_user: Optional[str]
    owner_group: Optional[str]
    compute_history_: Optional[List[ComputeHistory]]
    task_: Optional[RecordTask]
    service_: Optional[RecordService]
    comments_: Optional[List[RecordComment]]
    native_files_: Optional[Dict[str, NativeFile]]
    def __init__(self, client: Incomplete | None = None, **kwargs) -> None: ...
    def __init_subclass__(cls) -> None: ...
    @classmethod
    def get_subclass(cls, record_type: str) -> Type[BaseRecord]: ...
    def propagate_client(self, client) -> None: ...
    @property
    def offline(self) -> bool: ...
    @property
    def children_status(self) -> Dict[RecordStatusEnum, int]: ...
    @property
    def compute_history(self) -> List[ComputeHistory]: ...
    @property
    def task(self) -> Optional[RecordTask]: ...
    @property
    def service(self) -> Optional[RecordService]: ...
    def get_waiting_reason(self) -> Dict[str, Any]: ...
    @property
    def comments(self) -> Optional[List[RecordComment]]: ...
    @property
    def native_files(self) -> Optional[Dict[str, NativeFile]]: ...
    @property
    def stdout(self) -> Optional[str]: ...
    @property
    def stderr(self) -> Optional[str]: ...
    @property
    def error(self) -> Optional[Dict[str, Any]]: ...
    @property
    def provenance(self) -> Optional[Provenance]: ...

class RecordAddBodyBase(RestModelBase):
    tag: None
    priority: PriorityEnum
    owner_group: Optional[str]
    find_existing: bool

class RecordModifyBody(RestModelBase):
    record_ids: List[int]
    status: Optional[RecordStatusEnum]
    priority: Optional[PriorityEnum]
    tag: Optional[str]
    comment: Optional[str]

class RecordDeleteBody(RestModelBase):
    record_ids: List[int]
    soft_delete: bool
    delete_children: bool

class RecordRevertBody(RestModelBase):
    revert_status: RecordStatusEnum
    record_ids: List[int]

class RecordQueryFilters(QueryModelBase):
    record_id: Optional[List[int]]
    record_type: Optional[List[str]]
    manager_name: Optional[List[str]]
    status: Optional[List[RecordStatusEnum]]
    dataset_id: Optional[List[int]]
    parent_id: Optional[List[int]]
    child_id: Optional[List[int]]
    created_before: Optional[datetime]
    created_after: Optional[datetime]
    modified_before: Optional[datetime]
    modified_after: Optional[datetime]
    owner_user: Optional[List[Union[int, str]]]
    owner_group: Optional[List[Union[int, str]]]
    def parse_dates(cls, v): ...

class RecordQueryIterator(QueryIteratorBase[_Record_T]):
    record_type: Incomplete
    include: Incomplete
    def __init__(self, client, query_filters: RecordQueryFilters, record_type: Optional[str], include: Optional[Iterable[str]] = None) -> None: ...

def record_from_dict(data: Dict[str, Any], client: Any = None) -> BaseRecord: ...
def records_from_dicts(data: Sequence[Optional[Dict[str, Any]]], client: Any = None) -> List[Optional[BaseRecord]]: ...
