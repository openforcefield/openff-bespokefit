"""Models used in executor services."""

from typing import Generic, TypeVar

import numpy as np

from openff.bespokefit._pydantic import BaseModel, Field, GenericModel

_T = TypeVar("_T")


class Error(BaseModel):
    """Model for handling an error."""

    type: str = Field(..., description="The type of exception that was raised.")
    message: str = Field(..., description="The message associated with the exception.")

    traceback: str | None = Field(
        None,
        description="The traceback associated with the exception",
    )


class Link(BaseModel):
    """Model for handling a link."""

    self: str = Field(..., description="The API endpoint associated with this object.")
    id: str = Field(..., description="The unique id associated with this object.")

    def __lt__(self, other):
        return self.id.__lt__(other.id)

    def __gt__(self, other):
        return self.id.__gt__(other.id)

    def __eq__(self, other):
        return (
            type(self) is type(other)
            and self.id.__eq__(other.id)
            and self.self.__eq__(other.self)
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.id, self.self))


class PaginatedCollection(GenericModel, Generic[_T]):
    """Model for handling a paginated collection."""

    self: str = Field(..., description="The API endpoint associated with this object.")

    prev: str | None = Field(
        None,
        description="The API endpoint to use to retrieve the previous items in the "
        "collection when paginating.",
    )
    next: str | None = Field(
        None,
        description="The API endpoint to use to retrieve the next items in the "
        "collection when paginating.",
    )

    contents: list[_T] = Field(..., description="The contents of the collection.")

    class Config:
        """Pydantic Config."""

        json_encoders = {np.ndarray: lambda v: v.flatten().tolist()}
