"""
Here we register all optimizers with bespokefit.
"""
from typing import Dict, List, Union

from openff.bespokefit.exceptions import OptimizerError
from openff.bespokefit.optimizers.forcebalance import ForceBalanceOptimizer
from openff.bespokefit.optimizers.model import Optimizer

optimizers: Dict[str, Optimizer] = {}


def register_optimizer(optimizer: Optimizer, replace: bool = False) -> None:
    """
    Register a new valid optimizer with bespokefit.

    Parameters
    ----------
    optimizer: Optimizer
        The optimizer class that should be registered.
    replace: bool
        If the optimizer should replace another optimizer registered with the same name.

    Raises
    ------
    OptimizerError
        If the optimizer is already registered or if the optimizer object is not compatible.
    """

    if issubclass(type(optimizer), Optimizer):
        optimizer_name = optimizer.optimizer_name.lower()
        if optimizer_name not in optimizers or (
            optimizer_name in optimizers and replace
        ):
            optimizers[optimizer_name] = optimizer
        else:
            raise OptimizerError(
                f"An optimizer is already registered under the name {optimizer.optimizer_name}, to replace this please use the `replace=True` flag."
            )
    else:
        raise OptimizerError(
            f"The optimizer {optimizer} could not be registered it must be a subclass of openff.bespokefit.optimzers.Optimizer"
        )


def deregister_optimizer(optimizer: Union[Optimizer, str]) -> None:
    """
    Remove an optimizer from the list of valid optimizers.

    Parameters
    ----------
    optimizer: Union[Optimizer, str]
        The optimizer class or name of the class that should be removed.
    """

    try:
        optimizer_name = optimizer.optimizer_name.lower()
    except AttributeError:
        optimizer_name = optimizer.lower()

    opt = optimizers.pop(optimizer_name, None)
    if opt is None:
        raise OptimizerError(
            f"The optimizer {optimizer} was not registered with bespokefit."
        )


def get_optimizer(optimizer_name: str, **kwargs) -> Optimizer:
    """
    Get the optimizer class from the list of registered optimizers in bespokefit by name.

    Parameters
    ----------
    optimizer_name: str
        The `optimizer_name` attribute of the optimizer that should be fetched.
    kwargs: dict
        Any kwargs that should be passed into the optimizer.

    Returns
    -------
    Optimizer
        The requested optimizer matching the given optimizer name.
    """

    opt = optimizers.get(optimizer_name.lower(), None)
    if opt is None:
        raise OptimizerError(
            f"The optimizer {optimizer_name} was not registered with bespokefit."
        )

    if kwargs:
        return opt.parse_obj(kwargs)
    else:
        return opt


def list_optimizers() -> List[str]:
    """
    Get the list of registered optimizers with bespokefit.

    Returns
    -------
    List[str]
        A list of the optimizer classes registered.
    """

    return list(optimizers.keys())


# register the built in optimizers
register_optimizer(ForceBalanceOptimizer())
