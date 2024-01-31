from .record_models import QCSpecification as QCSpecification, SinglepointDriver as SinglepointDriver
from _typeshed import Incomplete
from qcarchivetesting.testing_classes import QCATestingSnowflake as QCATestingSnowflake
from qcportal.record_models import RecordStatusEnum as RecordStatusEnum
from typing import List, Optional

all_includes: Incomplete

def test_singlepoint_models_lowercase() -> None: ...
def test_singlepoint_models_basis_convert() -> None: ...
def test_singlepointrecord_model(snowflake: QCATestingSnowflake, includes: Optional[List[str]]): ...
