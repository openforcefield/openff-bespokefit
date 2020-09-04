"""
The optimizer model abstract class.
"""

import abc
from typing import Dict, List, Union

from pydantic import BaseModel, validator

from ..exceptions import TargetRegisterError
from ..targets.model import Target


class Optimizer(BaseModel, abc.ABC):
    """
    This is the abstract basic Optimizer class that each optimizer should use.
    """

    optimizer_name: str
    optimizer_description: str
    optimization_targets: List[
        Target
    ] = []  # this is the actual targets that are to be executed in the optimizaion

    @validator("optimizer_name")
    def _set_optimizer_name(cls, optimizer_name: str) -> str:
        """
        Make sure that the optimizer name is the same as the cls.__name__
        """
        if optimizer_name.lower() == cls.__name__.lower():
            return optimizer_name
        else:
            return cls.__name__

    class Config:
        validate_assignment = True
        arbitrary_types_allowed = True

    # this is shared across optimizers so we have to separate by optimizer
    _all_targets: Dict[str, Dict[str, Target]] = {}

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

        elif target.name in self._get_registered_targets().keys():
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
                return target.parse_obj(kwargs)

    @classmethod
    def register_target(cls, target: Target, overwrite: bool = False) -> None:
        """
        Take a target and register it with the optimizer under an alias name which is used to call the target.

        Parameters:
            target: The target class which is to be registered with the optimizer.
            overwrite: If the alias is already registered overwrite with the new target data with no exception.
        """

        current_targets = cls._get_registered_targets()
        if (target.name not in current_targets) or (
            target.name in current_targets and overwrite
        ):
            try:
                cls._all_targets[cls.__name__][target.name] = target
            except KeyError:
                cls._all_targets[cls.__name__] = {target.name: target}
        else:
            raise TargetRegisterError(
                f"The alias {target.name} has already been registered with this optimizer; to update use overwrite = `True`."
            )

    @classmethod
    def deregister_target(cls, target_name: str) -> None:
        """
        Remove a registered target from the optimizer.

        Parameters:
            target_name: The name of the target that should be removed.
        """

        current_targets = cls._get_registered_targets()
        if target_name in current_targets:
            del cls._all_targets[cls.__name__][target_name]

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
    def optimize(
        self, workflow: "WorkflowSchema", initial_forcefield: str
    ) -> "WorkflowSchema":
        """
        This is the main function of the optimizer which is called when the optimizer is put in a workflow.
        It should loop over the targets and assert they are registered and then dispatch compute and optimization.
        """
        raise NotImplementedError()
