from typing import Dict, List, Optional, Union

from openff.fragmenter.fragment import (
    FragmentationResult,
    PfizerFragmenter,
    WBOFragmenter,
)
from pydantic import Field

from openff.bespokefit.executor.services.models import Link
from openff.bespokefit.executor.utilities.typing import Status
from openff.bespokefit.utilities.pydantic import BaseModel


class FragmenterGETResponse(Link):
    """The object model returned by a GET request."""

    status: Status = Field("waiting", description="The status of the fragmentation.")

    result: Optional[FragmentationResult] = Field(
        ..., description="The result of the fragmentation if any was produced."
    )

    error: Optional[str] = Field(
        ..., description="The error raised while fragmenting if any."
    )

    links: Dict[str, str] = Field(
        {}, description="Links to resources associated with the model.", alias="_links"
    )


class FragmenterPOSTBody(BaseModel):
    """The object model expected by a POST request."""

    cmiles: str = Field(
        ..., description="The CMILES representation of the molecule to fragment."
    )
    fragmenter: Optional[Union[PfizerFragmenter, WBOFragmenter]] = Field(
        ..., description="The fragmentation engine to use."
    )

    target_bond_smarts: Optional[List[str]] = Field(
        ...,
        description="A list of SMARTS patterns that should be used to identify the "
        "bonds within the parent molecule to grow fragments around. Each SMARTS pattern "
        "should include **two** indexed atoms that correspond to the two atoms involved "
        "in the central bond.",
    )


class FragmenterPOSTResponse(Link):
    """The object model returned by a POST request."""
