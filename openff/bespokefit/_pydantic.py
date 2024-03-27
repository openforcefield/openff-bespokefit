"""A set of common utilities and types useful for building pydantic models."""

import numpy

try:
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
except ImportError:
    from pydantic import BaseModel as PydanticBaseModel
    from pydantic import (  # noqa
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
    from pydantic.generics import GenericModel  # noqa


class BaseModel(PydanticBaseModel):
    """The base model from which all data models within the package should inherit."""

    class Config:
        """Pydantic config."""

        extra = Extra.forbid

        json_encoders = {numpy.ndarray: lambda v: v.flatten().tolist()}


class SchemaBase(BaseModel):
    """The base model from which all data models within the package should inherit."""

    class Config:
        """Pydantic config."""

        allow_mutation = True
        validate_assignment = True


class ClassBase(SchemaBase):
    """
    A custom model for dealing with custom types.

    A base model which facilitates building classes which are able to take advantage
    of the pydantic machinery, but which are not expected to be used as data models and
    hence may of fields of arbitrary (e.g. an OFF Molecule) types.
    """

    class Config:
        """Default Pydantic config."""

        arbitrary_types_allowed = True
        validate_assignment = True
