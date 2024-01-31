from _typeshed import Incomplete
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, IPvAnyAddress as IPvAnyAddress, constr as constr
from qcportal.base_models import QueryIteratorBase as QueryIteratorBase, QueryModelBase as QueryModelBase, QueryProjModelBase as QueryProjModelBase, RestModelBase as RestModelBase, validate_list_to_single as validate_list_to_single
from typing import Any, Dict, List, Optional, Union

class GroupByEnum(str, Enum):
    user: str
    day: str
    hour: str
    country: str
    subdivision: str

class DeleteBeforeDateBody(RestModelBase):
    before: Optional[datetime]

class AccessLogQueryFilters(QueryProjModelBase):
    module: Optional[List[None]]
    method: Optional[List[None]]
    user: Optional[List[Union[int, str]]]
    before: Optional[datetime]
    after: Optional[datetime]
    def parse_dates(cls, v): ...

class AccessLogEntry(BaseModel):
    class Config:
        extra: Incomplete
    id: int
    timestamp: datetime
    method: str
    module: Optional[str]
    full_uri: Optional[str]
    request_duration: Optional[float]
    request_bytes: Optional[float]
    response_bytes: Optional[float]
    user: Optional[str]
    ip_address: Optional[IPvAnyAddress]
    user_agent: Optional[str]
    country_code: Optional[str]
    subdivision: Optional[str]
    city: Optional[str]
    ip_lat: Optional[float]
    ip_long: Optional[float]

class AccessLogQueryIterator(QueryIteratorBase[AccessLogEntry]):
    def __init__(self, client, query_filters: AccessLogQueryFilters) -> None: ...

class AccessLogSummaryFilters(RestModelBase):
    group_by: GroupByEnum
    before: Optional[datetime]
    after: Optional[datetime]
    def validate_lists(cls, v): ...
    def parse_dates(cls, v): ...

class AccessLogSummaryEntry(BaseModel):
    class Config:
        extra: Incomplete
    module: Optional[str]
    method: str
    count: int
    request_duration_info: List[float]
    response_bytes_info: List[float]

class AccessLogSummary(BaseModel):
    class Config:
        extra: Incomplete
    entries: Dict[str, List[AccessLogSummaryEntry]]

class ErrorLogQueryFilters(QueryModelBase):
    error_id: Optional[List[int]]
    user: Optional[List[Union[int, str]]]
    before: Optional[datetime]
    after: Optional[datetime]
    def parse_dates(cls, v): ...

class ErrorLogEntry(BaseModel):
    class Config:
        extra: Incomplete
    id: int
    error_date: datetime
    qcfractal_version: str
    error_text: Optional[str]
    user: Optional[str]
    request_path: Optional[str]
    request_headers: Optional[str]
    request_body: Optional[str]

class ErrorLogQueryIterator(QueryIteratorBase[ErrorLogEntry]):
    def __init__(self, client, query_filters: ErrorLogQueryFilters) -> None: ...

class ServerStatsQueryFilters(QueryModelBase):
    before: Optional[datetime]
    after: Optional[datetime]
    def validate_lists(cls, v): ...
    def parse_dates(cls, v): ...

class ServerStatsEntry(BaseModel):
    class Config:
        extra: Incomplete
    id: int
    timestamp: datetime
    collection_count: Optional[int]
    molecule_count: Optional[int]
    record_count: Optional[int]
    outputstore_count: Optional[int]
    access_count: Optional[int]
    error_count: Optional[int]
    task_queue_status: Optional[Dict[str, Any]]
    service_queue_status: Optional[Dict[str, Any]]
    db_total_size: Optional[int]
    db_table_size: Optional[int]
    db_index_size: Optional[int]
    db_table_information: Dict[str, Any]

class ServerStatsQueryIterator(QueryIteratorBase[ServerStatsEntry]):
    def __init__(self, client, query_filters: ServerStatsQueryFilters) -> None: ...
