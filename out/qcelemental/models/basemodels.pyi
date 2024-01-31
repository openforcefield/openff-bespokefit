from pathlib import Path
from pydantic import BaseModel, BaseSettings
from qcelemental.util import deserialize as deserialize, serialize as serialize
from qcelemental.util.autodocs import AutoPydanticDocGenerator as AutoPydanticDocGenerator
from typing import Any, Dict, Optional, Set, Union

class ProtoModel(BaseModel):
    class Config:
        allow_mutation: bool
        extra: str
        json_encoders: Dict[str, Any]
        serialize_default_excludes: Set
        serialize_skip_defaults: bool
        force_skip_defaults: bool
    def __init_subclass__(cls, **kwargs) -> None: ...
    @classmethod
    def parse_raw(cls, data: Union[bytes, str], *, encoding: Optional[str] = None) -> ProtoModel: ...
    @classmethod
    def parse_file(cls, path: Union[str, Path], *, encoding: Optional[str] = None) -> ProtoModel: ...
    def dict(self, **kwargs) -> Dict[str, Any]: ...
    def serialize(self, encoding: str, *, include: Optional[Set[str]] = None, exclude: Optional[Set[str]] = None, exclude_unset: Optional[bool] = None, exclude_defaults: Optional[bool] = None, exclude_none: Optional[bool] = None) -> Union[bytes, str]: ...
    def json(self, **kwargs): ...
    def compare(self, other: Union['ProtoModel', BaseModel], **kwargs) -> bool: ...

class AutodocBaseSettings(BaseSettings):
    def __init_subclass__(cls) -> None: ...

qcschema_draft: str
