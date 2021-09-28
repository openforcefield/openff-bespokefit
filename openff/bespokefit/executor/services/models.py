from typing import Optional

from pydantic import BaseModel, Field


class Error(BaseModel):

    type: str = Field(..., description="The type of exception that was raised.")
    message: str = Field(..., description="The message associated with the exception.")

    traceback: Optional[str] = Field(
        None, description="The traceback associated with the exception"
    )


class Link(BaseModel):

    id: str = Field(..., description="The unique id associated with this object.")
    href: str = Field(..., description="The API endpoint associated with this object.")

    def __lt__(self, other):
        return self.id.__lt__(other.id)

    def __gt__(self, other):
        return self.id.__gt__(other.id)

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.id.__eq__(other.id)
            and self.href.__eq__(other.href)
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.id, self.href))
