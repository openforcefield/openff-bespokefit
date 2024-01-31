from .basemodels import ProtoModel as ProtoModel, qcschema_draft as qcschema_draft
from .basis import BasisSet as BasisSet
from _typeshed import Incomplete
from enum import Enum
from pydantic.typing import ReprArgs as ReprArgs
from typing import Any, Dict, Optional, Union

ndarray_encoder: Incomplete

class Provenance(ProtoModel):
    creator: str
    version: str
    routine: str
    class Config(ProtoModel.Config):
        canonical_repr: bool
        extra: str
        def schema_extra(schema, model) -> None: ...

class Model(ProtoModel):
    method: str
    basis: Optional[Union[str, BasisSet]]
    class Config(ProtoModel.Config):
        canonical_repr: bool
        extra: str

class DriverEnum(str, Enum):
    energy: str
    gradient: str
    hessian: str
    properties: str
    deferred: str
    def derivative_int(self): ...

class ComputeError(ProtoModel):
    error_type: str
    error_message: str
    extras: Optional[Dict[str, Any]]
    class Config:
        repr_style: Incomplete
    def __repr_args__(self) -> ReprArgs: ...

class FailedOperation(ProtoModel):
    id: str
    input_data: Any
    success: bool
    error: ComputeError
    extras: Optional[Dict[str, Any]]
    def __repr_args__(self) -> ReprArgs: ...

qcschema_input_default: str
qcschema_output_default: str
qcschema_optimization_input_default: str
qcschema_optimization_output_default: str
qcschema_torsion_drive_input_default: str
qcschema_torsion_drive_output_default: str
qcschema_molecule_default: str
