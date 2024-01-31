from pydantic import BaseModel as BaseModel, Extra as Extra, constr as constr
from qcportal.base_models import RestModelBase as RestModelBase
from qcportal.managers import ManagerName as ManagerName
from typing import Dict, List

class TaskClaimBody(RestModelBase):
    name_data: ManagerName
    programs: Dict[None, List[str]]
    tags: List[str]
    limit: int

class TaskReturnBody(RestModelBase):
    name_data: ManagerName
    results_compressed: Dict[int, bytes]
