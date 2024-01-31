from ..util import provenance_stamp as provenance_stamp
from .basemodels import ProtoModel as ProtoModel
from .common_models import ComputeError as ComputeError, DriverEnum as DriverEnum, Model as Model, Provenance as Provenance, qcschema_input_default as qcschema_input_default, qcschema_optimization_input_default as qcschema_optimization_input_default, qcschema_optimization_output_default as qcschema_optimization_output_default, qcschema_torsion_drive_input_default as qcschema_torsion_drive_input_default, qcschema_torsion_drive_output_default as qcschema_torsion_drive_output_default
from .molecule import Molecule as Molecule
from .results import AtomicResult as AtomicResult
from enum import Enum
from pydantic import conlist as conlist, constr as constr
from pydantic.typing import ReprArgs as ReprArgs
from typing import Any, Dict, List, Optional, Tuple

class TrajectoryProtocolEnum(str, Enum):
    all: str
    initial_and_final: str
    final: str
    none: str

class OptimizationProtocols(ProtoModel):
    trajectory: TrajectoryProtocolEnum
    class Config:
        force_skip_defaults: bool

class QCInputSpecification(ProtoModel):
    schema_name: None
    schema_version: int
    driver: DriverEnum
    model: Model
    keywords: Dict[str, Any]
    extras: Dict[str, Any]

class OptimizationInput(ProtoModel):
    id: Optional[str]
    hash_index: Optional[str]
    schema_name: None
    schema_version: int
    keywords: Dict[str, Any]
    extras: Dict[str, Any]
    protocols: OptimizationProtocols
    input_specification: QCInputSpecification
    initial_molecule: Molecule
    provenance: Provenance
    def __repr_args__(self) -> ReprArgs: ...

class OptimizationResult(OptimizationInput):
    schema_name: None
    final_molecule: Optional[Molecule]
    trajectory: List[AtomicResult]
    energies: List[float]
    stdout: Optional[str]
    stderr: Optional[str]
    success: bool
    error: Optional[ComputeError]
    provenance: Provenance

class OptimizationSpecification(ProtoModel):
    schema_name: None
    schema_version: int
    procedure: str
    keywords: Dict[str, Any]
    protocols: OptimizationProtocols

class TDKeywords(ProtoModel):
    dihedrals: List[Tuple[int, int, int, int]]
    grid_spacing: List[int]
    dihedral_ranges: Optional[List[Tuple[int, int]]]
    energy_decrease_thresh: Optional[float]
    energy_upper_limit: Optional[float]

class TorsionDriveInput(ProtoModel):
    schema_name: None
    schema_version: int
    keywords: TDKeywords
    extras: Dict[str, Any]
    input_specification: QCInputSpecification
    initial_molecule: None
    optimization_spec: OptimizationSpecification
    provenance: Provenance

class TorsionDriveResult(TorsionDriveInput):
    schema_name: None
    schema_version: int
    final_energies: Dict[str, float]
    final_molecules: Dict[str, Molecule]
    optimization_history: Dict[str, List[OptimizationResult]]
    stdout: Optional[str]
    stderr: Optional[str]
    success: bool
    error: Optional[ComputeError]
    provenance: Provenance

def Optimization(*args, **kwargs): ...
