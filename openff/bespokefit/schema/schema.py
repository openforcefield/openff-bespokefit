"""Schemas."""

from typing import Literal, Optional

from pydantic import Field

from openff.bespokefit.utilities.pydantic import BaseModel

Status = Literal["waiting", "running", "errored", "success"]


class Error(BaseModel):
    """Store an error."""

    type: str = Field(..., description="The type of exception that was raised.")
    message: str = Field(..., description="The message associated with the exception.")

    traceback: Optional[str] = Field(
        None,
        description="The traceback associated with the exception",
    )
