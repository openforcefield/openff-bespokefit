"""A set of common utilities and types useful for building pydantic models."""
import numpy as np
import pydantic
from pydantic import Extra


class BaseModel(pydantic.BaseModel):
    """The base model from which all data models within the package should inherit."""

    class Config:
        """Pydantic config."""

        extra = Extra.forbid

        json_encoders = {np.ndarray: lambda v: v.flatten().tolist()}


class SchemaBase(BaseModel):
    """The base model from which all data models within the package should inherit."""

    class Config:
        """Pydantic config."""

        allow_mutation = True
        validate_assignment = True


class ClassBase(SchemaBase):
    """
    A custom base class.

    A base model which facilitates building classes which are able to take advantage
    of the pydantic machinery, but which are not expected to be used as data models and
    hence may of fields of arbitrary (e.g. an OFF Molecule) types.

    """

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
        validate_assignment = True
