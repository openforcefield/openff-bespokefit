"""Mels for fragmenter steps."""

from openff.fragmenter.fragment import (
    FragmentationResult,
    PfizerFragmenter,
    WBOFragmenter,
)

from openff.bespokefit._pydantic import BaseModel, Field
from openff.bespokefit.executor.services.models import Link
from openff.bespokefit.executor.utilities.typing import Status


class FragmenterGETResponse(Link):
    """The object model returned by a fragmenter GET request."""

    status: Status = Field("waiting", description="The status of the fragmentation.")

    result: FragmentationResult | None = Field(
        ...,
        description="The result of the fragmentation if any was produced.",
    )

    error: str | None = Field(
        ...,
        description="The error raised while fragmenting if any.",
    )

    links: dict[str, str] = Field(
        {},
        description="Links to resources associated with the model.",
        alias="_links",
    )


class FragmenterPOSTBody(BaseModel):
    """The object model expected by a fragmenter POST request."""

    cmiles: str = Field(
        ...,
        description="The CMILES representation of the molecule to fragment.",
    )
    fragmenter: PfizerFragmenter | WBOFragmenter | None = Field(
        ...,
        description="The fragmentation engine to use.",
    )

    target_bond_smarts: list[str] | None = Field(
        ...,
        description="A list of SMARTS patterns that should be used to identify the "
        "bonds within the parent molecule to grow fragments around. Each SMARTS pattern "
        "should include **two** indexed atoms that correspond to the two atoms involved "
        "in the central bond.",
    )


class FragmenterPOSTResponse(Link):
    """The object model returned by a POST request."""
