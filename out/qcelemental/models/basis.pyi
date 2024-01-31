from ..exceptions import ValidationError as ValidationError
from .basemodels import ProtoModel as ProtoModel, qcschema_draft as qcschema_draft
from enum import Enum
from pydantic import ConstrainedInt, constr as constr
from typing import Dict, List, Optional

class NonnegativeInt(ConstrainedInt):
    ge: int

class HarmonicType(str, Enum):
    spherical: str
    cartesian: str

class ElectronShell(ProtoModel):
    angular_momentum: List[NonnegativeInt]
    harmonic_type: HarmonicType
    exponents: List[float]
    coefficients: List[List[float]]
    class Config(ProtoModel.Config):
        def schema_extra(schema, model) -> None: ...
    def nfunctions(self) -> int: ...
    def is_contracted(self) -> bool: ...

class ECPType(str, Enum):
    scalar: str
    spinorbit: str

class ECPPotential(ProtoModel):
    ecp_type: ECPType
    angular_momentum: List[NonnegativeInt]
    r_exponents: List[int]
    gaussian_exponents: List[float]
    coefficients: List[List[float]]
    class Config(ProtoModel.Config):
        def schema_extra(schema, model) -> None: ...

class BasisCenter(ProtoModel):
    electron_shells: List[ElectronShell]
    ecp_electrons: int
    ecp_potentials: Optional[List[ECPPotential]]
    class Config(ProtoModel.Config):
        def schema_extra(schema, model) -> None: ...

class BasisSet(ProtoModel):
    schema_name: None
    schema_version: int
    name: str
    description: Optional[str]
    center_data: Dict[str, BasisCenter]
    atom_map: List[str]
    nbf: Optional[int]
    class Config(ProtoModel.Config):
        def schema_extra(schema, model) -> None: ...
