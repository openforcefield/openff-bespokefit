"""
The optimizer model abstract class.
"""

import abc
from typing import Dict, List, Union

from pydantic import validator

from openff.bespokefit.common_structures import SchemaBase
from openff.bespokefit.exceptions import TargetRegisterError
from openff.bespokefit.schema import OptimizationSchema
from openff.bespokefit.targets.model import Target


class Optimizer(SchemaBase, abc.ABC):
    """
    This is the abstract basic Optimizer class that each optimizer should use.
    """

    optimizer_name: str
    optimizer_description: str
    optimization_targets: List[
        Target
    ] = []  # this is the actual targets that are to be executed in the optimizaion

    class Config:
        validate_assignment = True
        arbitrary_types_allowed = True
        fields = {
            "optimizer_name": {
                "description": "The name of the optimizer used to rebuild the optimizer model."
            },
            "optimizer_description": {
                "description": "A short description of the optimizer and links to more info."
            },
            "optimization_targets": {
                "description": "The list of optimization targets."
            },
        }

    # this is shared across optimizers so we have to separate by optimizer
    _all_targets: Dict[str, Dict[str, Target]] = {}

    @validator("optimizer_name")
    def _set_optimizer_name(cls, optimizer_name: str) -> str:
        """
        Make sure that the optimizer name is the same as the cls.__name__
        """
        if optimizer_name.lower() == cls.__name__.lower():
            return optimizer_name
        else:
            return cls.__name__

    def set_optimization_target(self, target: Union[Target, str], **kwargs) -> None:
        """
        Add a valid registered optimization target to the list of targets to be executed.

        Parameters:
            target: Either the target instance or the name of the registered target which should be added to the optimization targets list.
            kwargs: Any kwargs that should be used to build the target, these are only used when the target name is supplied to add the target.
        """
        if isinstance(target, str):
            self.optimization_targets.append(
                self.get_optimization_target(target, **kwargs)
            )

        elif target.name.lower() in self._get_registered_targets().keys():
            self.optimization_targets.append(target)

        else:
            raise TargetRegisterError(
                f"The requested target {target.name} is not registered with the optimizer, {self.__class__.__name__}"
            )

    def clear_optimization_targets(self) -> None:
        """
        Clear out the optimization targets currently set into the optimizer.
        """

        self.optimization_targets = []

    def get_optimization_target(self, target_name: str, **kwargs) -> Target:
        """
        Get an optimization target initialized using the given kwargs if it has been registered with the optimizer.

        Parameters:
            target_name: The name of the target that was registered with the optimizer
            kwargs: The kwargs that should be passed into the init.
        """
        targets = self._get_registered_targets()
        for name, target in targets.items():
            if name.lower() == target_name.lower():
                if kwargs:
                    return target.parse_obj(kwargs)
                else:
                    return target
        raise TargetRegisterError(
            f"No target is registered to this optimizer under the name {target_name.lower()}"
        )

    @classmethod
    def register_target(cls, target: Target, replace: bool = False) -> None:
        """
        Take a target and register it with the optimizer under an alias name which is used to call the target.

        Parameters
        ----------
        target: Target
            The target class which is to be registered with the optimizer.
        replace: bool
            If the alias is already registered replaced with the new target data with no exception.

        Raises
        ------
        TargetRegisterError
            If the target has already been registered.
        """

        current_targets = cls._get_registered_targets()
        if (target.name.lower() not in current_targets) or (
            target.name.lower() in current_targets and replace
        ):
            try:
                cls._all_targets[cls.__name__][target.name.lower()] = target
            except KeyError:
                cls._all_targets[cls.__name__] = {target.name.lower(): target}
        else:
            raise TargetRegisterError(
                f"The alias {target.name.lower()} has already been registered with this optimizer; to update use overwrite = `True`."
            )

    @classmethod
    def deregister_target(cls, target_name: str) -> None:
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

        current_targets = cls._get_registered_targets()
        if target_name.lower() in current_targets:
            del cls._all_targets[cls.__name__][target_name.lower()]
        else:
            raise TargetRegisterError(
                f"No target with the name {target_name.lower()} was registered."
            )

    @classmethod
    def _get_registered_targets(cls) -> Dict[str, Target]:
        """
        Internal method to get the registered targets for this specific optimizer.
        """
        return cls._all_targets.get(cls.__name__, {})

    @classmethod
    def get_registered_targets(cls) -> List[Target]:
        """
        Get all of the targets registered for this optimizer.

        Returns:
            A list of the registered targets and details describing their function.
        """

        return list(cls._get_registered_targets().values())

    @classmethod
    def get_registered_target_names(cls) -> List[str]:
        """
        Get the names of the registered targets for this optimizer.
        """
        return list(cls._get_registered_targets().keys())

    @abc.abstractmethod
    def provenance(self) -> Dict:
        """
        This function should detail the programs with the version information called during the running od the optimizer.

        Returns:
            A dictionary containing the information about the optimizer called.
        """

        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def is_available(cls) -> bool:
        """
        This method should check that installation requirements are met before trying to run the optimizer.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def optimize(self, schema: OptimizationSchema) -> OptimizationSchema:
        """
        This is the main function of the optimizer which is called when the optimizer is put in a workflow.
        It should loop over the targets and assert they are registered and then dispatch compute and optimization.
        """
        raise NotImplementedError()
