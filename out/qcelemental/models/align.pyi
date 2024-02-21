from .basemodels import ProtoModel
from .types import Array
from typing import Optional

__all__ = ['AlignmentMill']

class AlignmentMill(ProtoModel):
    shift: Optional[Array[float]]
    rotation: Optional[Array[float]]
    atommap: Optional[Array[int]]
    mirror: bool
    class Config:
        force_skip_defaults: bool
    def pretty_print(self, label: str = '') -> str: ...
    def align_coordinates(self, geom, *, reverse: bool = False) -> Array: ...
    def align_atoms(self, ats): ...
    def align_vector(self, vec): ...
    def align_gradient(self, grad) -> Array: ...
    def align_hessian(self, hess) -> Array: ...
    def align_vector_gradient(self, mu_derivatives): ...
    def align_system(self, geom, mass, elem, elez, uniq, *, reverse: bool = False): ...
    def align_mini_system(self, geom, uniq, *, reverse: bool = False): ...