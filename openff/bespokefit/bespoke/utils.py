from typing import List

from openff.qcsubmit.serializers import deserialize, serialize

from openff.bespokefit.schema.fitting import BespokeOptimizationSchema


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
