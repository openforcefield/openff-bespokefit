from typing import List

from openff.qcsubmit.serializers import deserialize, serialize

from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults


def serialize_schema(schemas: List[BespokeOptimizationSchema], file_name: str) -> None:
    """
    Serialize the list of bespoke schemas to file.
    """

    serialize(
        {opt_schema.id: opt_schema.json(indent=2) for opt_schema in schemas},
        file_name=file_name,
    )


def deserialize_schema(file_name: str) -> List[BespokeOptimizationSchema]:
    """
    Deserialize a list of bespoke optimization schemas from a file.
    """
    data = deserialize(file_name=file_name)
    return [BespokeOptimizationSchema.parse_raw(opt) for opt in data.values()]


def serialize_results(
    results: List[BespokeOptimizationResults], file_name: str
) -> None:
    """
    Serialize a list of bespoke optimization results schema to file.
    """
    serialize(
        {result.input_schema.id: result.json(indent=2) for result in results},
        file_name=file_name,
    )


def deserialize_results(file_name: str) -> List[BespokeOptimizationResults]:
    """
    Deserialize a list of bespoke optimization results schema from a file.
    """
    data = deserialize(file_name=file_name)
    return [BespokeOptimizationResults.parse_raw(result) for result in data.values()]
