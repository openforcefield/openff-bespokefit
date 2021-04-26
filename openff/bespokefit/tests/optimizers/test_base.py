"""
Unit test ability to add and remove new optimizers.
"""

import pytest

from openff.bespokefit.exceptions import OptimizerError
from openff.bespokefit.optimizers import BaseOptimizer, ForceBalanceOptimizer
from openff.bespokefit.optimizers.base import (
    deregister_optimizer,
    get_optimizer,
    list_optimizers,
    register_optimizer,
)


def test_list_optimizers():
    """
    Make sure all registered optimizers are returned
    """

    # get optimizers in lower case
    optimizers = list_optimizers()
    assert "forcebalance" in optimizers


@pytest.mark.parametrize(
    "optimizer_name, expected", [("forcebalance", ForceBalanceOptimizer)]
)
def test_get_optimizer(optimizer_name, expected):
    assert get_optimizer(optimizer_name) == expected


def test_get_optimizer_missing():

    expected_match = "The optimizer fake-optimizer was not registered with bespokefit."

    with pytest.raises(OptimizerError, match=expected_match):
        get_optimizer(optimizer_name="fake-optimizer")


def test_register_deregister_optimizer():
    class CustomOptimizer(BaseOptimizer):
        """A dummy optimizer class to use in tests."""

        @classmethod
        def name(cls):
            return "CustomOptimizer"

    assert CustomOptimizer.name().lower() not in list_optimizers()
    register_optimizer(CustomOptimizer)
    assert CustomOptimizer.name().lower() in list_optimizers()
    deregister_optimizer(CustomOptimizer)
    assert CustomOptimizer.name().lower() not in list_optimizers()


def test_deregister_optimizer_error():

    with pytest.raises(OptimizerError, match="was not registered with"):
        deregister_optimizer("fake-name")


def test_register_optimizer_type_error():

    with pytest.raises(OptimizerError, match="must be a subclass"):
        register_optimizer(float)


def test_register_optimizer_already_registered_error():

    with pytest.raises(OptimizerError, match="An optimizer is already registered"):
        register_optimizer(ForceBalanceOptimizer)
