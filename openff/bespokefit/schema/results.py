import abc
from typing import Dict, List, Optional, Union

from openff.toolkit.typing.engines.smirnoff import ForceField
from pydantic import Field
from typing_extensions import Literal

from openff.bespokefit.exceptions import OptimizerError
from openff.bespokefit.schema.bespoke.smirks import BespokeSmirksParameter
from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationSchema,
    Status,
)
from openff.bespokefit.schema.smirnoff import SmirksType
from openff.bespokefit.utilities.pydantic import SchemaBase

OptimizationSchemaType = Union[OptimizationSchema, BespokeOptimizationSchema]


class BaseOptimizationResults(SchemaBase, abc.ABC):
    """The base class for data models which store the results of an optimization."""

    type: Literal["base"] = "base"

    input_schema: Optional[OptimizationSchemaType] = Field(
        None, description="The schema defining the input to the optimization."
    )
    provenance: Dict[str, str] = Field(
        ..., description="The versions of the software used to generate the results."
    )

    status: Status = Field(
        Status.Undefined, description="The status of the optimization."
    )

    # TODO: Other fields which would be good to include.

    # objective_function: List[float] = Field(
    #     ..., description="The value of the objective function at each iteration."
    # )


class OptimizationResults(BaseOptimizationResults):
    """A class for storing the results of a general force field optimization."""

    type: Literal["general"] = "general"

    refit_force_field: Optional[str] = Field(
        None, description="The XML contents of the refit force field."
    )

    # TODO: Store the actual molecule attributes


class BespokeOptimizationResults(BaseOptimizationResults):
    """A class for storing the results of a bespoke force field optimization."""

    type: Literal["bespoke"] = "bespoke"

    final_smirks: List[BespokeSmirksParameter] = Field(
        [],
        description="A list of the refit force field parameters.",
    )

    def get_final_force_field(
        self,
        drop_out_value: Optional[float] = None,
    ) -> ForceField:
        """
        Generate the final bespoke forcefield for this molecule by collecting together
        all optimized smirks.

        Parameters:
            drop_out_value: Any torsion force constants below this value will be set to 0
                as they are probably negligible.
        """
        from openff.bespokefit.utilities.smirnoff import ForceFieldEditor

        # TODO change this to a util function remove from target base class
        # check that all optimizations are finished
        if self.status != Status.Complete:

            raise OptimizerError(
                "The molecule has not completed all optimization stages which are "
                "required to generate the final force field."
            )

        if self.final_smirks is None:
            raise OptimizerError(
                "The optimization status is complete but no optimized smirks were "
                "found."
            )

        # get all of the target smirks
        target_smirks = self.final_smirks

        if drop_out_value is not None:
            # loop over all of the target smirks and drop and torsion k values lower
            # than the drop out
            for smirk in target_smirks:

                if smirk.type == SmirksType.ProperTorsions:
                    for p, term in smirk.terms.items():
                        if abs(float(term.k.split("*")[0])) < drop_out_value:
                            term.k = 0

        # the final fitting force field should have all final smirks propagated through
        fitting_ff = ForceFieldEditor(
            force_field_name=self.input_schema.initial_force_field
        )
        fitting_ff.add_smirks(smirks=target_smirks, parameterize=False)

        return fitting_ff.force_field
