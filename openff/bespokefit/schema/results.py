import abc
from typing import Any, Dict, Optional

from openff.toolkit.typing.engines.smirnoff import ForceField
from pydantic import Field
from simtk import unit
from typing_extensions import Literal

from openff.bespokefit.schema import Error, Status
from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationSchema,
)
from openff.bespokefit.schema.smirnoff import BaseSMIRKSParameter
from openff.bespokefit.utilities.pydantic import SchemaBase


class BaseOptimizationResults(SchemaBase, abc.ABC):
    """The base class for data models which store the results of an optimization."""

    type: Literal["base"] = "base"

    input_schema: Optional[Any] = Field(
        None, description="The schema defining the input to the optimization."
    )
    provenance: Dict[str, str] = Field(
        {}, description="The versions of the software used to generate the results."
    )

    status: Status = Field("waiting", description="The status of the optimization.")

    error: Optional[Error] = Field(
        None, description="The error, if any, that was raised while running."
    )

    refit_force_field: Optional[str] = Field(
        None, description="The XML contents of the refit force field."
    )

    # TODO: Other fields which would be good to include.

    # objective_function: List[float] = Field(
    #     ..., description="The value of the objective function at each iteration."
    # )

    @property
    def initial_parameter_values(self) -> Dict[BaseSMIRKSParameter, unit.Quantity]:
        """A list of the refit force field parameters."""

        return self.input_schema.initial_parameter_values

    @property
    def refit_parameter_values(
        self,
    ) -> Optional[Dict[BaseSMIRKSParameter, unit.Quantity]]:
        """A list of the refit force field parameters."""

        if self.refit_force_field is None:
            return None

        refit_force_field = ForceField(self.refit_force_field)

        return {
            parameter: getattr(
                refit_force_field[parameter.type].parameters[parameter.smirks],
                attribute,
            )
            for parameter in self.input_schema.parameters
            for attribute in parameter.attributes
        }


class OptimizationResults(BaseOptimizationResults):
    """A class for storing the results of a general force field optimization."""

    type: Literal["general"] = "general"

    input_schema: Optional[OptimizationSchema] = Field(
        None, description="The schema defining the input to the optimization."
    )


class BespokeOptimizationResults(BaseOptimizationResults):
    """A class for storing the results of a bespoke force field optimization."""

    type: Literal["bespoke"] = "bespoke"

    input_schema: Optional[BespokeOptimizationSchema] = Field(
        None, description="The schema defining the input to the optimization."
    )
