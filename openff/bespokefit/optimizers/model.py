"""
The optimizer model abstract class.
"""

import abc
import copy
import os
import shutil
from collections import defaultdict
from typing import Dict, Optional, Type

from openff.toolkit.typing.engines.smirnoff import ForceField
from openff.utilities import temporary_cd

from openff.bespokefit.exceptions import OptimizerError, TargetRegisterError
from openff.bespokefit.schema.fitting import OptimizationStageSchema
from openff.bespokefit.schema.optimizers import OptimizerSchema
from openff.bespokefit.schema.results import OptimizationStageResults
from openff.bespokefit.schema.targets import BaseTargetSchema

TargetSchemaType = Type[BaseTargetSchema]


class BaseOptimizer(abc.ABC):
    """
    This is the abstract basic BaseOptimizer class that each optimizer should use.
    """

    # this is shared across optimizers so we have to separate by optimizer
    _registered_targets: Dict[str, Dict[str, TargetSchemaType]] = defaultdict(dict)

    @classmethod
    @abc.abstractmethod
    def name(cls) -> str:
        """Returns the friendly name of the optimizer."""
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def description(cls) -> str:
        """Returns a friendly description of the optimizer."""
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def provenance(cls) -> Dict:
        """
        This function should detail the programs with the version information called
        during the running od the optimizer.

        Returns:
            A dictionary containing the information about the optimizer called.
        """
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def is_available(cls) -> bool:
        """
        This method should check that installation requirements are met before trying to
        run the optimizer.
        """
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def _schema_class(cls) -> Type[OptimizerSchema]:
        """The schema associated with this optimizer."""
        raise NotImplementedError

    @classmethod
    def get_registered_targets(cls) -> Dict[str, TargetSchemaType]:
        """
        Internal method to get the registered targets for this specific optimizer.
        """
        return copy.deepcopy(cls._registered_targets.get(cls.__name__, {}))

    @classmethod
    def register_target(
        cls, target_type: TargetSchemaType, replace: bool = False
    ) -> None:
        """
        Take a target and register it with the optimizer under an alias name which is
        used to call the target.

        Parameters
        ----------
        target_type
            The type of target to be registered with the optimizer.
        replace
            If the alias is already registered replaced with the new target data with no
            exception.

        Raises
        ------
        TargetRegisterError
            If the target has already been registered.
        """

        if not issubclass(target_type, BaseTargetSchema):

            raise TargetRegisterError(
                f"The {target_type.__name__} does not inherit from the "
                f"``BaseTargetSchema`` target base class."
            )

        target_name = target_type.__fields__["type"].default

        current_targets = cls.get_registered_targets()

        if (target_name.lower() not in current_targets) or (
            target_name.lower() in current_targets and replace
        ):
            cls._registered_targets[cls.__name__][target_name.lower()] = target_type
        else:
            raise TargetRegisterError(
                f"The alias {target_name.lower()} has already been registered with "
                f"this optimizer; to update use overwrite = `True`."
            )

    @classmethod
    def deregister_target(cls, target_name: str):
        """
        Remove a registered target from the optimizer.

        Parameters
        ----------
        target_name: str
            The name of the target that should be removed.

        Raises
        ------
        TargetRegisterError
            If no target is registered under the name to be removed.
        """

        current_targets = cls.get_registered_targets()

        if target_name.lower() in current_targets:
            del cls._registered_targets[cls.__name__][target_name.lower()]
        else:
            raise TargetRegisterError(
                f"No target with the name {target_name.lower()} was registered."
            )

    @classmethod
    def _validate_schema(cls, schema: OptimizationStageSchema):
        """Validates that a particular optimization schema can be used with this
        optimizer.
        """

        if not isinstance(schema.optimizer, cls._schema_class()):

            raise OptimizerError(
                f"The ``{cls.__name__}`` optimizer can only be used with "
                f"optimization schemas which specify a {cls._schema_class().__name__} "
                f"optimizer, not a {schema.optimizer.__class__.__name__}."
            )

        registered_targets = cls.get_registered_targets()

        for target in schema.targets:

            if target.type.lower() in registered_targets:
                continue

            raise TargetRegisterError(
                f"The {target.type} target type is not registered with the "
                f"{cls.__class__.__name__} optimizer."
            )

    @classmethod
    @abc.abstractmethod
    def _prepare(
        cls,
        schema: OptimizationStageSchema,
        initial_force_field: ForceField,
        root_directory: str,
    ):
        """The internal implementation of the main ``prepare`` method. The input
        ``schema`` is assumed to have been validated before being passed to this
        method.
        """
        raise NotImplementedError()

    @classmethod
    def prepare(
        cls,
        schema: OptimizationStageSchema,
        initial_force_field: ForceField,
        root_directory: str,
    ):
        """Prepares the optimization by creating any required inputs and setting up
        the required environment."""

        cls._validate_schema(schema)
        cls._prepare(schema, initial_force_field, root_directory)

    @classmethod
    def _optimize(
        cls, schema: OptimizationStageSchema, initial_force_field: ForceField
    ) -> OptimizationStageResults:
        """The internal implementation of the main ``optimize`` method. The input
        ``schema`` is assumed to have been validated before being passed to this
        method.
        """
        raise NotImplementedError()

    @classmethod
    def optimize(
        cls,
        schema: OptimizationStageSchema,
        initial_force_field: ForceField,
        keep_files: bool = False,
        root_directory: Optional[str] = None,
    ) -> OptimizationStageResults:
        """
        This is the main function of the optimizer which is called when the optimizer is
        put in a workflow.

        It should loop over the targets and assert they are registered and then dispatch
        compute and optimization.
        """

        try:

            if root_directory is not None:
                os.makedirs(root_directory, exist_ok=True)

            with temporary_cd(root_directory):

                cls.prepare(schema, initial_force_field, ".")
                results = cls._optimize(schema, initial_force_field)

        finally:

            if (
                root_directory is not None
                and not keep_files
                and os.path.isdir(root_directory)
            ):
                shutil.rmtree(root_directory, ignore_errors=True)

        return results
