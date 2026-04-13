"""A set of common utilities and types useful for building pydantic models."""

import numpy
from pydantic.v1 import BaseModel as PydanticBaseModel
from pydantic.v1 import (
    BaseSettings,
    Extra,
    Field,
    PositiveFloat,
    PositiveInt,
    ValidationError,
    conint,
    conlist,
    parse_file_as,
    parse_obj_as,
    parse_raw_as,
    validator,
)
from pydantic.v1.generics import GenericModel


class BaseModel(PydanticBaseModel):
    """The base model from which all data models within the package should inherit."""

    class Config:
        extra = Extra.forbid

        json_encoders = {numpy.ndarray: lambda v: v.flatten().tolist()}


class SchemaBase(BaseModel):
    """The base model from which all data models within the package should inherit."""

    class Config:
        allow_mutation = True
        validate_assignment = True


class ClassBase(SchemaBase):
    """A base model which facilitates building classes which are able to take advantage
    of the pydantic machinery, but which are not expected to be used as data models and
    hence may of fields of arbitrary (e.g. an OFF Molecule) types."""

    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True
