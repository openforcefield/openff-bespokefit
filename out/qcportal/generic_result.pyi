from qcelemental.models.common_models import ComputeError as ComputeError, ProtoModel, Provenance as Provenance
from typing import Any, Dict, Optional
from typing_extensions import Literal

class GenericTaskResult(ProtoModel):
    schema_name: Literal['qca_generic_task_result']
    id: int
    results: Any
    stdout: Optional[str]
    stderr: Optional[str]
    success: bool
    provenance: Provenance
    extras: Dict[str, Any]
    error: Optional[ComputeError]
