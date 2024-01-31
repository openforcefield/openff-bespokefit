from _typeshed import Incomplete
from pydantic import BaseModel
from typing import Any, Dict, Optional

class Datum(BaseModel):
    numeric: bool
    label: str
    units: str
    data: Any
    comment: str
    doi: Optional[str]
    glossary: str
    class Config:
        extra: str
        allow_mutation: bool
        json_encoders: Incomplete
    def __init__(self, label, units, data, *, comment: Incomplete | None = None, doi: Incomplete | None = None, glossary: Incomplete | None = None, numeric: bool = True) -> None: ...
    def must_be_numerical(cls, v, values, **kwargs): ...
    def dict(self, *args, **kwargs): ...
    def to_units(self, units: Incomplete | None = None): ...

def print_variables(qcvars: Dict[str, 'Datum']) -> str: ...
