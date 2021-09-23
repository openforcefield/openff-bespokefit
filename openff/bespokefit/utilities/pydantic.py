"""A set of common utilities and types useful for building pydantic models.
"""
import numpy as np
from pydantic import BaseModel


class SchemaBase(BaseModel):
    """The base model from which all data models within the package should inherit."""

    class Config:

        allow_mutation = True
        validate_assignment = True

        json_encoders = {np.ndarray: lambda v: v.flatten().tolist()}


class ClassBase(SchemaBase):
    """A base model which facilitates building classes which are able to take advantage
    of the pydantic machinery, but which are not expected to be used as data models and
    hence may of fields of arbitrary (e.g. an OFF Molecule) types."""

    class Config:

        arbitrary_types_allowed = True
        validate_assignment = True
