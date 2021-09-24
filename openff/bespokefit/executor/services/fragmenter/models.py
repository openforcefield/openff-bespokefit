from typing import List, Optional, Union

from openff.fragmenter.fragment import (
    FragmentationResult,
    PfizerFragmenter,
    WBOFragmenter,
)
from pydantic import Field

from openff.bespokefit.executor.utilities.typing import Status
from openff.bespokefit.utilities.pydantic import BaseModel


class FragmenterBaseResponse(BaseModel):

    fragmentation_id: str = Field(
        ..., description="The ID associated with the fragmentation."
    )


class FragmenterGETStatusResponse(BaseModel):

    fragmentation_status: Status = Field(
        "waiting", description="The status of the fragmentation."
    )


class FragmenterGETResultResponse(BaseModel):

    fragmentation_result: Optional[FragmentationResult] = Field(
        ..., description="The result of the fragmentation if any was produced."
    )


class FragmenterGETErrorResponse(BaseModel):

    fragmentation_error: Optional[str] = Field(
        ..., description="The error raised while fragmenting if any."
    )


class FragmenterGETResponse(
    FragmenterBaseResponse,
    FragmenterGETStatusResponse,
    FragmenterGETResultResponse,
    FragmenterGETErrorResponse,
):
    """The object model returned by a GET request."""


class FragmenterPOSTBody(BaseModel):
    """The object model expected by a POST request."""

    cmiles: str = Field(
        ..., description="The CMILES representation of the molecule to fragment."
    )
    fragmenter: Union[PfizerFragmenter, WBOFragmenter] = Field(
        ..., description="The fragmentation engine to use."
    )

    target_bond_smarts: List[str] = Field(
        ...,
        description="A list of SMARTS patterns that should be used to identify the "
        "bonds within the parent molecule to grow fragments around. Each SMARTS pattern "
        "should include **two** indexed atoms that correspond to the two atoms involved "
        "in the central bond.",
    )


class FragmenterPOSTResponse(FragmenterBaseResponse):
    """The object model returned by a POST request."""
