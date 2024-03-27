"""Schema for results."""

from __future__ import annotations

import abc
from typing import Any, Literal

from openff.toolkit.typing.engines.smirnoff import ForceField
from openff.units import unit

from openff.bespokefit._pydantic import Field, SchemaBase
from openff.bespokefit.schema import Error, Status
from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationSchema,
)
from openff.bespokefit.schema.smirnoff import BaseSMIRKSParameter


class OptimizationStageResults(SchemaBase, abc.ABC):
    """The base class for data models which store the results of an optimization."""

    provenance: dict[str, str] = Field(
        {},
        description="The versions of the software used to generate the results.",
    )

    status: Status = Field("waiting", description="The status of the optimization.")

    error: Error | None = Field(
        None,
        description="The error, if any, that was raised while running.",
    )

    refit_force_field: str | None = Field(
        None,
        description="The XML contents of the refit force field.",
    )

    # TODO: Other fields which would be good to include.

    # objective_function: List[float] = Field(
    #     ..., description="The value of the objective function at each iteration."
    # )


class BaseOptimizationResults(SchemaBase, abc.ABC):
    """A class for storing the results of a general force field optimization."""

    type: Literal["base-results"] = "base-results"

    input_schema: Any | None = Field(
        None,
        description="The schema defining the input to the optimization.",
    )

    stages: list[OptimizationStageResults] = Field(
        [],
        description="The results of each of the fitting states.",
    )

    @property
    def initial_parameter_values(
        self,
    ) -> dict[BaseSMIRKSParameter, dict[str, unit.Quantity]] | None:
        """A list of the refit force field parameters."""
        return (
            None
            if self.input_schema is None
            else self.input_schema.initial_parameter_values
        )

    @property
    def refit_force_field(self) -> str | None:
        """Return the final refit force field."""
        return (
            None if not self.status == "success" else self.stages[-1].refit_force_field
        )

    @property
    def refit_parameter_values(
        self,
    ) -> dict[BaseSMIRKSParameter, dict[str, unit.Quantity]] | None:
        """A list of the refit force field parameters."""
        if self.input_schema is None or not self.status == "success":
            return None

        refit_force_field = ForceField(self.stages[-1].refit_force_field)

        return {
            parameter: {
                attribute: getattr(
                    refit_force_field[parameter.type].parameters[parameter.smirks],
                    attribute,
                )
                for attribute in parameter.attributes
            }
            for stage in self.input_schema.stages
            for parameter in stage.parameters
        }

    @property
    def status(self) -> Status:
        """Return the status."""
        if (
            len(self.stages) == 0
            or all(stage.status == "waiting" for stage in self.stages)
            or self.input_schema is None
        ):
            return "waiting"

        if any(stage.status == "errored" for stage in self.stages):
            return "errored"

        if len(self.stages) == len(self.input_schema.stages) and all(
            stage.status == "success" for stage in self.stages
        ):
            return "success"

        return "running"


class OptimizationResults(BaseOptimizationResults):
    """A class for storing the results of a general force field optimization."""

    type: Literal["general"] = "general"

    input_schema: OptimizationSchema | None = Field(
        None,
        description="The schema defining the input to the optimization.",
    )


class BespokeOptimizationResults(BaseOptimizationResults):
    """A class for storing the results of a bespoke force field optimization."""

    type: Literal["bespoke"] = "bespoke"

    input_schema: BespokeOptimizationSchema | None = Field(
        None,
        description="The schema defining the input to the optimization.",
    )
