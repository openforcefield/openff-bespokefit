import numpy as np
from _typeshed import Incomplete
from collections.abc import Generator
from typing import Any, Dict

class TypedArray(np.ndarray):
    @classmethod
    def __get_validators__(cls) -> Generator[Incomplete, None, None]: ...
    @classmethod
    def validate(cls, v): ...
    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None: ...

class ArrayMeta(type):
    def __getitem__(self, dtype): ...

class Array(np.ndarray, metaclass=ArrayMeta): ...
