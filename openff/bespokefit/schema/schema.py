from typing import Optional

from pydantic import BaseModel, Field
from typing_extensions import Literal

Status = Literal["waiting", "running", "errored", "success"]


class Error(BaseModel):

    type: str = Field(..., description="The type of exception that was raised.")
    message: str = Field(..., description="The message associated with the exception.")

    traceback: Optional[str] = Field(
        None, description="The traceback associated with the exception"
    )
