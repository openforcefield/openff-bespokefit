from ..util import provenance_stamp as provenance_stamp
from .basemodels import ProtoModel as ProtoModel, qcschema_draft as qcschema_draft
from .basis import BasisSet as BasisSet
from .common_models import ComputeError as ComputeError, DriverEnum as DriverEnum, Model as Model, Provenance as Provenance, qcschema_input_default as qcschema_input_default, qcschema_output_default as qcschema_output_default
from .molecule import Molecule as Molecule
from .types import Array as Array
from enum import Enum
from pydantic import constr as constr
from pydantic.typing import ReprArgs as ReprArgs
from typing import Any, Dict, Optional, Union

class AtomicResultProperties(ProtoModel):
    calcinfo_nbasis: Optional[int]
    calcinfo_nmo: Optional[int]
    calcinfo_nalpha: Optional[int]
    calcinfo_nbeta: Optional[int]
    calcinfo_natom: Optional[int]
    nuclear_repulsion_energy: Optional[float]
    return_energy: Optional[float]
    return_gradient: Optional[Array[float]]
    return_hessian: Optional[Array[float]]
    scf_one_electron_energy: Optional[float]
    scf_two_electron_energy: Optional[float]
    scf_vv10_energy: Optional[float]
    scf_xc_energy: Optional[float]
    scf_dispersion_correction_energy: Optional[float]
    scf_dipole_moment: Optional[Array[float]]
    scf_quadrupole_moment: Optional[Array[float]]
    scf_total_energy: Optional[float]
    scf_total_gradient: Optional[Array[float]]
    scf_total_hessian: Optional[Array[float]]
    scf_iterations: Optional[int]
    mp2_same_spin_correlation_energy: Optional[float]
    mp2_opposite_spin_correlation_energy: Optional[float]
    mp2_singles_energy: Optional[float]
    mp2_doubles_energy: Optional[float]
    mp2_correlation_energy: Optional[float]
    mp2_total_energy: Optional[float]
    mp2_dipole_moment: Optional[Array[float]]
    ccsd_same_spin_correlation_energy: Optional[float]
    ccsd_opposite_spin_correlation_energy: Optional[float]
    ccsd_singles_energy: Optional[float]
    ccsd_doubles_energy: Optional[float]
    ccsd_correlation_energy: Optional[float]
    ccsd_total_energy: Optional[float]
    ccsd_dipole_moment: Optional[Array[float]]
    ccsd_iterations: Optional[int]
    ccsd_prt_pr_correlation_energy: Optional[float]
    ccsd_prt_pr_total_energy: Optional[float]
    ccsd_prt_pr_dipole_moment: Optional[Array[float]]
    ccsdt_correlation_energy: Optional[float]
    ccsdt_total_energy: Optional[float]
    ccsdt_dipole_moment: Optional[Array[float]]
    ccsdt_iterations: Optional[int]
    ccsdtq_correlation_energy: Optional[float]
    ccsdtq_total_energy: Optional[float]
    ccsdtq_dipole_moment: Optional[Array[float]]
    ccsdtq_iterations: Optional[int]
    class Config(ProtoModel.Config):
        force_skip_defaults: bool
    def __repr_args__(self) -> ReprArgs: ...
    def dict(self, *args, **kwargs): ...

class WavefunctionProperties(ProtoModel):
    basis: BasisSet
    restricted: bool
    h_core_a: Optional[Array[float]]
    h_core_b: Optional[Array[float]]
    h_effective_a: Optional[Array[float]]
    h_effective_b: Optional[Array[float]]
    scf_orbitals_a: Optional[Array[float]]
    scf_orbitals_b: Optional[Array[float]]
    scf_density_a: Optional[Array[float]]
    scf_density_b: Optional[Array[float]]
    scf_fock_a: Optional[Array[float]]
    scf_fock_b: Optional[Array[float]]
    scf_eigenvalues_a: Optional[Array[float]]
    scf_eigenvalues_b: Optional[Array[float]]
    scf_occupations_a: Optional[Array[float]]
    scf_occupations_b: Optional[Array[float]]
    scf_coulomb_a: Optional[Array[float]]
    scf_coulomb_b: Optional[Array[float]]
    scf_exchange_a: Optional[Array[float]]
    scf_exchange_b: Optional[Array[float]]
    localized_orbitals_a: Optional[Array[float]]
    localized_orbitals_b: Optional[Array[float]]
    localized_fock_a: Optional[Array[float]]
    localized_fock_b: Optional[Array[float]]
    orbitals_a: Optional[str]
    orbitals_b: Optional[str]
    density_a: Optional[str]
    density_b: Optional[str]
    fock_a: Optional[str]
    fock_b: Optional[str]
    eigenvalues_a: Optional[str]
    eigenvalues_b: Optional[str]
    occupations_a: Optional[str]
    occupations_b: Optional[str]
    class Config(ProtoModel.Config):
        force_skip_defaults: bool

class WavefunctionProtocolEnum(str, Enum):
    all: str
    orbitals_and_eigenvalues: str
    occupations_and_eigenvalues: str
    return_results: str
    none: str

class ErrorCorrectionProtocol(ProtoModel):
    default_policy: bool
    policies: Optional[Dict[str, bool]]
    def allows(self, policy: str): ...

class NativeFilesProtocolEnum(str, Enum):
    all: str
    input: str
    none: str

class AtomicResultProtocols(ProtoModel):
    wavefunction: WavefunctionProtocolEnum
    stdout: bool
    error_correction: ErrorCorrectionProtocol
    native_files: NativeFilesProtocolEnum
    class Config:
        force_skip_defaults: bool

class AtomicInput(ProtoModel):
    id: Optional[str]
    schema_name: None
    schema_version: int
    molecule: Molecule
    driver: DriverEnum
    model: Model
    keywords: Dict[str, Any]
    protocols: AtomicResultProtocols
    extras: Dict[str, Any]
    provenance: Provenance
    class Config(ProtoModel.Config):
        def schema_extra(schema, model) -> None: ...
    def __repr_args__(self) -> ReprArgs: ...

class AtomicResult(AtomicInput):
    schema_name: None
    properties: AtomicResultProperties
    wavefunction: Optional[WavefunctionProperties]
    return_result: Union[float, Array[float], Dict[str, Any]]
    stdout: Optional[str]
    stderr: Optional[str]
    native_files: Dict[str, Any]
    success: bool
    error: Optional[ComputeError]
    provenance: Provenance

class ResultProperties(AtomicResultProperties):
    def __init__(self, *args, **kwargs) -> None: ...

class ResultProtocols(AtomicResultProtocols):
    def __init__(self, *args, **kwargs) -> None: ...

class ResultInput(AtomicInput):
    def __init__(self, *args, **kwargs) -> None: ...

class Result(AtomicResult):
    def __init__(self, *args, **kwargs) -> None: ...
