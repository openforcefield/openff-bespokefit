import abc
from typing import Dict, List, Optional

from openff.fragmenter.fragment import WBOFragmenter
from openff.toolkit.topology import Molecule
from openff.toolkit.typing.engines.smirnoff import ForceField
from openff.units import unit
from pydantic import Field, conlist
from typing_extensions import Literal

from openff.bespokefit.fragmentation import FragmentationEngine
from openff.bespokefit.schema.optimizers import OptimizerSchema
from openff.bespokefit.schema.smirnoff import (
    BaseSMIRKSParameter,
    SMIRNOFFHyperparameters,
    SMIRNOFFParameter,
)
from openff.bespokefit.schema.targets import TargetSchema
from openff.bespokefit.utilities.pydantic import SchemaBase
from openff.bespokefit.utilities.smirks import SMIRKSettings, SMIRKSType


class OptimizationStageSchema(SchemaBase, abc.ABC):
    """A schema that encodes a single stage in a multi-stage optimization.

    A common example may be one in which in the first stage a charge model is trained,
    followed by the valence parameters being trained, and finally the torsion parameters
    are trained.
    """

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
        description="The hyperparameters that describe how classes of parameters, e.g. "
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

    stages: conlist(OptimizationStageSchema, min_items=1) = Field(
        ...,
        description="The fitting stages that should be performed sequentially. The "
        "force field produced by one stage will be used as input to the subsequent "
        "stage.",
    )

    @property
    def initial_parameter_values(
        self,
    ) -> Dict[BaseSMIRKSParameter, Dict[str, unit.Quantity]]:
        """A list of the initial force field parameters that will be optimized."""

        initial_force_field = ForceField(self.initial_force_field)

        return {
            parameter: {
                attribute: getattr(
                    initial_force_field[parameter.type].parameters[parameter.smirks],
                    attribute,
                )
                for attribute in parameter.attributes
            }
            for stage in self.stages
            for parameter in stage.parameters
        }


class OptimizationSchema(BaseOptimizationSchema):
    """The schema for a general optimization that does not require bespoke stages such
    as fragmentation of bespoke QC calculations.
    """

    type: Literal["general"] = "general"


class BespokeOptimizationSchema(BaseOptimizationSchema):
    """A schema which encodes how a bespoke force field should be created for a specific
    molecule."""

    type: Literal["bespoke"] = "bespoke"

    smiles: str = Field(
        ...,
        description="The SMILES representation of the molecule to generate bespoke "
        "parameters for.",
    )

    initial_force_field_hash: str = Field(
        ...,
        description="The hash values of the initial input force field with "
        "no bespokefit modifications. Used for internal hashing",
    )

    fragmentation_engine: Optional[FragmentationEngine] = Field(
        WBOFragmenter(),
        description="The fragmentation engine that should be used to fragment the "
        "molecule. If no engine is provided the molecules will not be fragmented.",
    )

    target_torsion_smirks: Optional[List[str]] = Field(
        ...,
        description="A list of SMARTS patterns that should be used to identify the "
        "**bonds** within the target molecule to generate bespoke torsions around. Each "
        "SMARTS pattern should include **two** indexed atoms that correspond to the "
        "two atoms involved in the central bond."
        "\n"
        "By default bespoke torsion parameters (if requested) will be constructed for "
        "all non-terminal 'rotatable bonds'",
    )

    smirk_settings: SMIRKSettings = Field(
        SMIRKSettings(),
        description="The settings that should be used when generating SMIRKS patterns for this optimization stage.",
    )

    @property
    def molecule(self) -> Molecule:
        """Return the openff molecule of the mapped smiles."""
        return Molecule.from_mapped_smiles(self.smiles)

    @property
    def target_smirks(self) -> List[SMIRKSType]:
        """Returns a list of the target smirks types based on the selected hyper parameters.
        Used to determine which parameters should be fit.
        """
        return list(
            {
                SMIRKSType(parameter.type)
                for stage in self.stages
                for parameter in stage.parameter_hyperparameters
            }
        )
