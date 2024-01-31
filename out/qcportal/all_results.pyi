from .generic_result import GenericTaskResult as GenericTaskResult
from qcelemental.models import AtomicResult, FailedOperation, OptimizationResult
from typing import Union

AllResultTypes = Union[FailedOperation, AtomicResult, OptimizationResult, GenericTaskResult]
