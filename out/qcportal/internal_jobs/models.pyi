from ..base_models import QueryIteratorBase as QueryIteratorBase
from _typeshed import Incomplete
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from qcportal.base_models import QueryProjModelBase as QueryProjModelBase
from typing import Any, Dict, List, Optional, Union

class InternalJobStatusEnum(str, Enum):
    complete: str
    waiting: str
    running: str
    error: str
    cancelled: str

class InternalJob(BaseModel):
    class Config:
        extra: Incomplete
    id: int
    name: str
    status: InternalJobStatusEnum
    added_date: datetime
    scheduled_date: datetime
    started_date: Optional[datetime]
    last_updated: Optional[datetime]
    ended_date: Optional[datetime]
    runner_hostname: Optional[str]
    runner_uuid: Optional[str]
    progress: int
    function: str
    kwargs: Dict[str, Any]
    after_function: Optional[str]
    after_function_kwargs: Optional[Dict[str, Any]]
    result: Any
    user: Optional[str]

class InternalJobQueryFilters(QueryProjModelBase):
    job_id: Optional[List[int]]
    name: Optional[List[str]]
    user: Optional[List[Union[int, str]]]
    runner_hostname: Optional[List[str]]
    status: Optional[List[InternalJobStatusEnum]]
    last_updated_before: Optional[datetime]
    last_updated_after: Optional[datetime]
    added_before: Optional[datetime]
    added_after: Optional[datetime]
    scheduled_before: Optional[datetime]
    scheduled_after: Optional[datetime]
    def parse_dates(cls, v): ...

class InternalJobQueryIterator(QueryIteratorBase[InternalJob]):
    def __init__(self, client, query_filters: InternalJobQueryFilters) -> None: ...
