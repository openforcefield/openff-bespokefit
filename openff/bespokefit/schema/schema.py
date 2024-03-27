"""Schemas."""

from typing import Literal

from openff.bespokefit._pydantic import BaseModel, Field

Status = Literal["waiting", "running", "errored", "success"]


class Error(BaseModel):
    """Store an error."""

    type: str = Field(..., description="The type of exception that was raised.")
    message: str = Field(..., description="The message associated with the exception.")

    traceback: str | None = Field(
        None,
        description="The traceback associated with the exception",
    )
