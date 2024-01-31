from _typeshed import Incomplete
from pydantic import BaseModel
from typing import Generic, Iterator, List, Optional, TypeVar

T = TypeVar('T')

def validate_list_to_single(v): ...

class RestModelBase(BaseModel):
    class Config:
        extra: Incomplete
        validate_assignment: bool

class CommonBulkGetBody(RestModelBase):
    ids: List[int]
    include: Optional[List[str]]
    exclude: Optional[List[str]]
    missing_ok: bool

class CommonBulkGetNamesBody(RestModelBase):
    names: List[str]
    include: Optional[List[str]]
    exclude: Optional[List[str]]
    missing_ok: bool

class ProjURLParameters(RestModelBase):
    include: Optional[List[str]]
    exclude: Optional[List[str]]

class QueryModelBase(RestModelBase):
    limit: Optional[int]
    cursor: Optional[int]
    def validate_lists(cls, v): ...

class QueryProjModelBase(QueryModelBase, ProjURLParameters): ...

class QueryIteratorBase(Generic[T]):
    def __init__(self, client, query_filters: QueryModelBase, batch_limit: int) -> None: ...
    def reset(self) -> None: ...
    def __iter__(self) -> Iterator[T]: ...
    def __next__(self) -> T: ...
