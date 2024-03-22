"""
Here we register all optimizers with bespokefit.
"""

from typing import Union

from openff.bespokefit.exceptions import OptimizerError
from openff.bespokefit.optimizers.forcebalance import ForceBalanceOptimizer
from openff.bespokefit.optimizers.model import BaseOptimizer

_optimizers: dict[str, type[BaseOptimizer]] = {}


def register_optimizer(optimizer: type[BaseOptimizer], replace: bool = False) -> None:
    """
    Register a new valid optimizer with bespokefit.

    Parameters
    ----------
    optimizer: BaseOptimizer
        The optimizer class that should be registered.
    replace: bool
        If the optimizer should replace another optimizer registered with the same name.

    Raises
    ------
    OptimizerError
        If the optimizer is already registered or if the optimizer object is not
        compatible.

    """
    if not issubclass(optimizer, BaseOptimizer):
        raise OptimizerError(
            f"The optimizer {optimizer} could not be registered it must be a subclass "
            f"of openff.bespokefit.optimzers.BaseOptimizer",
        )

    optimizer_name = optimizer.name().lower()

    if optimizer_name in _optimizers and not replace:
        raise OptimizerError(
            f"An optimizer is already registered under the name {optimizer.name()}, "
            f"to replace this please use the `replace=True` flag.",
        )

    _optimizers[optimizer_name] = optimizer


def deregister_optimizer(
    optimizer: Union[BaseOptimizer, type[BaseOptimizer], str],
) -> None:
    """
    Remove an optimizer from the list of valid optimizers.

    Parameters
    ----------
    optimizer: Union[BaseOptimizer, str]
        The optimizer class or name of the class that should be removed.

    """
    if isinstance(optimizer, str):
        optimizer_name = optimizer.lower()
    else:
        optimizer_name = optimizer.name().lower()

    if _optimizers.pop(optimizer_name, None) is None:
        raise OptimizerError(
            f"The optimizer {optimizer} was not registered with bespokefit.",
        )


def get_optimizer(optimizer_name: str) -> type[BaseOptimizer]:
    """
    Get the optimizer class from the list of registered optimizers in bespokefit by name.

    Parameters
    ----------
    optimizer_name
        The name the optimizer class that should be fetched.

    Returns
    -------
        The requested optimizer matching the given optimizer name.

    """
    optimizer = _optimizers.get(optimizer_name.lower(), None)

    if optimizer is None:
        raise OptimizerError(
            f"The optimizer {optimizer_name} was not registered with bespokefit.",
        )

    return optimizer


def list_optimizers() -> list[str]:
    """
    Get the list of registered optimizers with bespokefit.

    Returns
    -------
        A list of the optimizer classes registered.

    """
    return list(_optimizers.keys())


# register the built in optimizers
register_optimizer(ForceBalanceOptimizer)
