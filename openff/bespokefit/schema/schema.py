"""
The base schema.
"""
from typing import Union

import numpy as np
from pydantic import BaseModel


class SchemaBase(BaseModel):
    """
    This is the Schema base class which is adapted to the other schema as required.
    """

    # set any enum fields here to make sure json and yaml work
    _enum_fields = []

    class Config:
        extra = "forbid"
        allow_mutation = True
        validate_assignment = True
        json_encoders = {
            np.ndarray: lambda v: v.flatten().tolist(),
        }

    def dict(
        self,
        *,
        include: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
        exclude: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
        by_alias: bool = False,
        skip_defaults: bool = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> "DictStrAny":

        # correct the enum dict rep
        data = super().dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )
        exclude = exclude or []
        for field in self._enum_fields:
            if field not in exclude:
                data[field] = getattr(self, field).value
        return data
