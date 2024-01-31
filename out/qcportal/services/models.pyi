from qcportal.record_models import BaseRecord as BaseRecord
from typing import Any, Dict, Optional
from typing_extensions import Literal

class ServiceSubtaskRecord(BaseRecord):
    record_type: Literal['servicesubtask']
    required_programs: Dict[str, Any]
    function: str
    function_kwargs: Dict[str, Any]
    results: Optional[Dict[str, Any]]
