import abc
import copy
from enum import Enum
from typing import Dict, List, Optional, Union

from openff.qcsubmit.datasets import (
    BasicDataset,
    OptimizationDataset,
    TorsiondriveDataset,
)
from openff.qcsubmit.results import (
    BasicCollectionResult,
    OptimizationCollectionResult,
    TorsionDriveCollectionResult,
)
from openforcefield.typing.engines.smirnoff import ForceField
from pydantic import Field
from typing_extensions import Literal

from openff.bespokefit.schema.bespoke import MoleculeSchema
from openff.bespokefit.schema.bespoke.smirks import BespokeSmirksParameter
from openff.bespokefit.schema.bespoke.tasks import (
    HessianTask,
    OptimizationTask,
    TorsionTask,
)
from openff.bespokefit.schema.data import BespokeQCData
from openff.bespokefit.schema.optimizers import OptimizerSchema
from openff.bespokefit.schema.smirks import SmirksParameter
from openff.bespokefit.schema.smirnoff import SmirksParameterSettings, SmirksType
from openff.bespokefit.schema.targets import TargetSchema
from openff.bespokefit.utilities.pydantic import SchemaBase
from openff.bespokefit.utilities.smirnoff import ForceFieldEditor


class Status(str, Enum):
    Complete = "COMPLETE"
    Optimizing = "OPTIMIZING"
    ErrorCycle = "ErrorCycle"
    ConvergenceError = "CONVERGENCE_ERROR"
    CollectionError = "COLLECTION_ERROR"
    Collecting = "COLLECTING"
    Ready = "READY"
    Prepared = "PREPARED"
    Undefined = "UNDEFINED"


class BaseOptimizationSchema(SchemaBase, abc.ABC):
    """A schema which encodes how a particular force field should be optimized against a
    set of fitting targets simultaneously.
    """

    type: Literal["base"] = "base"

    id: Optional[str] = Field(
        None, description="The unique id given to this optimization."
    )

    initial_force_field: str = Field(
        ..., description="The path to the force field to optimize."
    )

    optimizer: OptimizerSchema = Field(
        ...,
        description="The optimizer to use and its associated settings.",
    )

    targets: List[TargetSchema] = Field(
        [],
        description="The fittings targets to simultaneously optimize against.",
    )

    parameter_settings: List[SmirksParameterSettings] = Field(
        ...,
        description="The settings which describe how types of parameters, e.g. the "
        "force constant of a bond parameter, should be restrained during the "
        "optimisation such as through the inclusion of harmonic priors.",
    )

    @property
    def n_targets(self) -> int:
        """Returns the number of targets to be fit."""
        return len(self.targets)

    @abc.abstractmethod
    def get_fitting_force_field(self) -> ForceField:
        """Returns the force field object to be fit, complete with cosmetic attributes
        which specify the parameters to be refit.
        """
        raise NotImplementedError()

    # def add_target(self, target: TargetSchema) -> None:
    #     """
    #     Add a target schema to the optimizer making sure this target is registered
    #     with the optimizer.
    #
    #     TODO: Move to a validator?
    #     """
    #     from openff.bespokefit.optimizers import get_optimizer
    #
    #     opt = get_optimizer(optimizer_name=self.optimizer_name)
    #     if target.target_name.lower() in opt.get_registered_target_names():
    #         self.targets.append(target)
    #
    # def get_optimizer(self) -> "BaseOptimizer":
    #     """
    #     Get the requested optimizer with correct settings from the optimizer list.
    #     """
    #     from openff.bespokefit.optimizers import get_optimizer
    #
    #     settings = self.settings
    #     del settings["optimizer_name"]
    #     optimizer = get_optimizer(optimizer_name=self.optimizer_name, **settings)
    #     return optimizer


class OptimizationSchema(BaseOptimizationSchema):
    type: Literal["general"] = "general"

    target_parameters: List[SmirksParameter] = Field(
        ...,
        description="A list of the specific force field parameters that should be "
        "optimized.",
    )

    # TODO: Add a validator to make sure that for each type of parameter in
    #       ``target_parameters`` there is a corresponding setting in
    #       ``parameter_settings``.

    def get_fitting_force_field(self) -> ForceField:
        """Returns the force field object to be fit, complete with cosmetic attributes
        which specify the parameters to be refit.
        """

        force_field = ForceField(self.initial_force_field)

        for target_parameter in self.target_parameters:

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

    target_molecule: MoleculeSchema = Field(
        ...,
        description="The target molecule is defined along with information about its "
        "fragments.",
    )
    target_smirks: List[BespokeSmirksParameter] = Field(
        [],
        description="A List of all of the force field parameters that should be "
        "optimised.",
    )

    # TODO: Add a validator to make sure that for each type of parameter in
    #       ``target_smirks`` there is a corresponding setting in ``parameter_settings``.

    @property
    def n_tasks(self) -> int:
        """
        Calculate the number of unique tasks to be currently computed
        """
        return len(self.task_hashes)

    @property
    def task_hashes(self) -> List[str]:
        """
        Compute the task hashes for this molecule.
        """
        task_hash = set(
            task.get_task_hash()
            for target in self.targets
            if isinstance(target.reference_data, BespokeQCData)
            for task in target.reference_data.tasks
        )

        return list(task_hash)

    @property
    def ready_for_fitting(self) -> bool:

        return all(
            target.reference_data.ready_for_fitting
            for target in self.targets
            if isinstance(target.reference_data, BespokeQCData)
        )

    def _parameterize_smirks(self) -> List[BespokeSmirksParameter]:
        """For the set of target smirks use the parameter targets to tag the values
        which should be optimized.

        For example a BondSmirks with a parameter target of BondLength will have length
        set to be parameterized.
        """
        target_smirks = copy.deepcopy(self.target_smirks)

        for target_parameter in self.parameter_settings:

            for smirk in target_smirks:

                if (
                    target_parameter.parameter_type == smirk.type
                    and target_parameter.parameter_type == SmirksType.ProperTorsions
                ):

                    smirk.parameterize = [
                        f"k{i}" for i, _ in enumerate(smirk.terms, start=1)
                    ]

                elif target_parameter.parameter_type == smirk.type:
                    smirk.parameterize.add(target_parameter.target)

        return target_smirks

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

    def update_with_results(
        self,
        results: Union[
            BasicCollectionResult,
            OptimizationCollectionResult,
            TorsionDriveCollectionResult,
        ],
    ):
        """
        Take a list of results and search through the entries for a match where the
        results can be transferred.
        """
        for target in self.targets:

            if not isinstance(target.reference_data, BespokeQCData):
                continue

            target.reference_data.update_with_results(results)

    def get_task_map(
        self,
    ) -> Dict[str, List[Union[TorsionTask, OptimizationTask, HessianTask]]]:
        """
        Generate a mapping between all of the current tasks and their collection
        workflow stage.
        """
        hash_map = dict()

        for target in self.targets:

            if not isinstance(target.reference_data, BespokeQCData):
                continue

            target_map = target.reference_data.get_task_map()

            for key, tasks in target_map.items():
                hash_map.setdefault(key, []).extend(tasks)

        return hash_map

    def build_qcsubmit_datasets(
        self,
    ) -> List[Union[TorsiondriveDataset, OptimizationDataset, BasicDataset]]:
        """
        For each of the targets build a qcsubmit dataset of reference collection tasks.
        """
        datasets = [
            target.reference_data.build_qcsubmit_dataset()
            for target in self.targets
            if isinstance(target.reference_data, BespokeQCData)
        ]

        return [dataset for dataset in datasets if dataset is not None]


# class MultiStageOptimizationSchema(SchemaBase):
#     """A schema which defines how a full multi-stage fit should be performed."""
#
#     stages: List[Union[OptimizationSchema, BespokeOptimizationSchema]] = Field(
#         [],
#         description="The optimizations to be carried out sequentially in the fitting "
#         "procedure, whereby the output force field of one stage is the input to the "
#         "next stage.",
#     )
