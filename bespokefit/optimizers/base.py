"""
Here we register all optimizers with bespokefit.
"""
from typing import Dict, List, Union

from .forcebalance import ForceBalanceOptimizer
from .model import Optimizer

optimizers: Dict[str, Optimizer] = {}


def register_optimizer(optimizer: Optimizer) -> None:
    """
    Register a new valid optimizer with bespokefit.

    Parameters:
        optimizer: The optimizer class that should be registered.
    """

    if isinstance(optimizer, Optimizer):
        if optimizer.optimizer_name.lower() not in optimizers:
            optimizers[optimizer.optimizer_name.lower()] = optimizer


def deregister_optimizer(optimizer: Union[Optimizer, str]) -> None:
    """
    Remove an optimizer from the list of valid optimizers.

    Parameters:
        optimizer: The optimizer class or name of the class that should be removed.
    """

    if isinstance(optimizer, Optimizer):
        optimizer_name = optimizer.optimizer_name.lower()
    else:
        optimizer_name = optimizer.lower()

    opt = optimizers.pop(optimizer_name, None)
    if opt is None:
        raise KeyError(f"The optimizer {optimizer} was not registered with bespokefit.")


def get_optimizer(optimizer_name: str, **kwargs) -> Optimizer:
    """
    Get the optimizer class from the list of registered optimizers in bespokefit by name.

    Parameters:
        optimizer_name: The `optimizer_name` attribute of the optimizer that should be fetched.
        kwargs: Any kwargs that should be passed into the optimizer.

    Returns:
        The requested optimizer matching the given optimizer name.
    """

    opt = optimizers.get(optimizer_name.lower(), None)
    if opt is None:
        raise KeyError(
            f"The optimizer {optimizer_name} was not registered with bespokefit."
        )

    if kwargs:
        return opt.parse_obj(kwargs)
    else:
        return opt


def list_optimizers() -> List[str]:
    """
    Get the list of registered optimizers with bespokefit.

    Returns:
        A list of the optimizer classes registered.
    """

    return list(optimizers.keys())


# register the built in optimizers
register_optimizer(ForceBalanceOptimizer())
