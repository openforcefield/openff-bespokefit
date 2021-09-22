import abc
from typing import Dict, List, Optional

from openff.toolkit.typing.engines.smirnoff import ForceField
from pydantic import Field
from simtk import unit
from typing_extensions import Literal

from openff.bespokefit.schema.optimizers import OptimizerSchema
from openff.bespokefit.schema.smirnoff import (
    BaseSMIRKSParameter,
    SMIRNOFFHyperparameters,
    SMIRNOFFParameter,
)
from openff.bespokefit.schema.targets import TargetSchema
from openff.bespokefit.utilities.pydantic import SchemaBase
from openff.bespokefit.utilities.smirnoff import ForceFieldEditor


class BaseOptimizationSchema(SchemaBase, abc.ABC):
    """A schema which encodes how a particular force field should be optimized against a
    set of fitting targets simultaneously.
    """

    type: Literal["base"] = "base"

    id: Optional[str] = Field(
        None, description="The unique id given to this optimization."
    )

    initial_force_field: str = Field(
        ...,
        description="The path to the force field to optimize OR an XML serialized "
        "SMIRNOFF force field.",
    )

    optimizer: OptimizerSchema = Field(
        ...,
        description="The optimizer to use and its associated settings.",
    )

    # TODO: Add a validator to make sure that for each type of parameter in
    #       ``parameters`` there is a corresponding setting in
    #       ``parameter_hyperparameters``.
    parameters: List[SMIRNOFFParameter] = Field(
        ...,
        description="A list of the specific force field parameters that should be "
        "optimized.",
    )
    parameter_hyperparameters: List[SMIRNOFFHyperparameters] = Field(
        ...,
        description="The hyperparamerers that describe how classes of parameters, e.g. "
        "the force constant and length of a bond parameter, should be restrained during "
        "the optimisation such as through the inclusion of harmonic priors.",
    )

    targets: List[TargetSchema] = Field(
        [],
        description="The fittings targets to simultaneously optimize against.",
    )

    @property
    def n_targets(self) -> int:
        """Returns the number of targets to be fit."""
        return len(self.targets)

    @property
    def initial_parameter_values(self) -> Dict[BaseSMIRKSParameter, unit.Quantity]:
        """A list of the refit force field parameters."""

        initial_force_field = ForceField(self.initial_force_field)

        return {
            parameter: getattr(
                initial_force_field[parameter.type].parameters[parameter.smirks],
                attribute,
            )
            for parameter in self.parameters
            for attribute in parameter.attributes
        }

    @abc.abstractmethod
    def get_fitting_force_field(self) -> ForceField:
        """Returns the force field object to be fit, complete with cosmetic attributes
        which specify the parameters to be refit.
        """
        raise NotImplementedError()


class OptimizationSchema(BaseOptimizationSchema):
    """The schema for a general optimization that does not require bespoke stages such
    as fragmentation of bespoke QC calculations.
    """

    type: Literal["general"] = "general"

    def get_fitting_force_field(self) -> ForceField:
        """Returns the force field object to be fit, complete with cosmetic attributes
        which specify the parameters to be refit.
        """

        force_field = ForceField(self.initial_force_field)

        for target_parameter in self.parameters:

            parameter_handler = force_field.get_parameter_handler(target_parameter.type)
            parameter = parameter_handler.parameters[target_parameter.smirks]

            attributes_string = ", ".join(
                attribute
                for attribute in target_parameter.attributes
                if hasattr(parameter, attribute)
            )

            parameter.add_cosmetic_attribute("parameterize", attributes_string)

        return force_field


class BespokeOptimizationSchema(BaseOptimizationSchema):
    """A schema which encodes how a bespoke force field should be created for a specific
    molecule."""

    type: Literal["bespoke"] = "bespoke"

    smiles: str = Field(
        ...,
        description="The SMILES representation of the molecule to generate bespoke "
        "parameters for.",
    )

    # def _parameterize_smirks(self) -> List[BespokeSMIRKSParameter]:
    #     """For the set of target smirks use the parameter targets to tag the values
    #     which should be optimized.
    #
    #     For example a BondSMIRKS with a parameter target of BondLength will have length
    #     set to be parameterized.
    #     """
    #     target_smirks = copy.deepcopy(self.target_smirks)
    #
    #     for target_parameter in self.parameter_hyperparameters:
    #
    #         for smirk in target_smirks:
    #
    #             if (
    #                 target_parameter.parameter_type == smirk.type
    #                 and target_parameter.parameter_type == SMIRKSType.ProperTorsions
    #             ):
    #
    #                 smirk.parameterize = [
    #                     f"k{i}" for i, _ in enumerate(smirk.terms, start=1)
    #                 ]
    #
    #             elif target_parameter.parameter_type == smirk.type:
    #                 smirk.parameterize.add(target_parameter.target)
    #
    #     return target_smirks

    def get_fitting_force_field(self) -> ForceField:
        """Take the initial force field and edit it to add the new terms and return the
        OpenFF FF object.
        """

        # get all of the new target smirks
        target_smirks = self._parameterize_smirks()

        ff = ForceFieldEditor(self.initial_force_field)
        ff.add_smirks(target_smirks, parameterize=True)

        # if there are any parameters from a different optimization stage add them here
        # without parameterize tags
        return ff.force_field
