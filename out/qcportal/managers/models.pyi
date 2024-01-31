from ..base_models import QueryIteratorBase as QueryIteratorBase
from _typeshed import Incomplete
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, constr as constr
from qcportal.base_models import QueryProjModelBase as QueryProjModelBase, RestModelBase as RestModelBase
from typing import Dict, List, Optional

class ManagerStatusEnum(str, Enum):
    active: str
    inactive: str

class ManagerName(BaseModel):
    class Config:
        extra: Incomplete
    cluster: str
    hostname: str
    uuid: str
    @property
    def fullname(self): ...

class ComputeManagerLogEntry(BaseModel):
    class Config:
        extra: Incomplete
    id: int
    manager_id: int
    claimed: int
    successes: int
    failures: int
    rejected: int
    total_cpu_hours: float
    active_tasks: int
    active_cores: int
    active_memory: float
    timestamp: datetime

class ComputeManager(BaseModel):
    class Config:
        extra: Incomplete
    id: int
    name: str
    cluster: str
    hostname: str
    username: Optional[str]
    tags: List[str]
    claimed: int
    successes: int
    failures: int
    rejected: int
    total_cpu_hours: float
    active_tasks: int
    active_cores: int
    active_memory: float
    status: ManagerStatusEnum
    created_on: datetime
    modified_on: datetime
    manager_version: str
    programs: Dict[str, List[str]]
    log_: Optional[List[ComputeManagerLogEntry]]
    def propagate_client(self, client) -> None: ...
    @property
    def log(self): ...

class ManagerActivationBody(RestModelBase):
    name_data: ManagerName
    manager_version: str
    username: Optional[str]
    programs: Dict[None, List[str]]
    tags: List[None]
    def validate_tags(cls, v): ...
    def validate_programs(cls, v): ...

class ManagerUpdateBody(RestModelBase):
    status: ManagerStatusEnum
    active_tasks: int
    active_cores: int
    active_memory: float
    total_cpu_hours: float

class ManagerQueryFilters(QueryProjModelBase):
    manager_id: Optional[List[int]]
    name: Optional[List[str]]
    cluster: Optional[List[str]]
    hostname: Optional[List[str]]
    status: Optional[List[ManagerStatusEnum]]
    modified_before: Optional[datetime]
    modified_after: Optional[datetime]
    def parse_dates(cls, v): ...

class ManagerQueryIterator(QueryIteratorBase[ComputeManager]):
    def __init__(self, client, query_filters: ManagerQueryFilters) -> None: ...
