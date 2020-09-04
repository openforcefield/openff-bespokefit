"""
The base schema.
"""

import numpy as np
from pydantic import BaseModel


class SchemaBase(BaseModel):
    """
    This is the Schema base class which is adapted to the other schema as required.
    """

    class Config:
        allow_mutation = True
        validate_assignment = True
        json_encoders = {
            np.ndarray: lambda v: v.flatten().tolist(),
        }
