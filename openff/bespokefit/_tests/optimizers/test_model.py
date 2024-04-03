"""
Unit test ability to add and remove new optimizers as well as the various optimizer classes.
"""

import pytest
from openff.toolkit.typing.engines.smirnoff import ForceField

from openff.bespokefit.exceptions import OptimizerError, TargetRegisterError
from openff.bespokefit.optimizers import BaseOptimizer, ForceBalanceOptimizer
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.targets import (
    BaseTargetSchema,
    TorsionProfileTargetSchema,
)


def test_get_registered_targets():
    """
    Test listing all of the registered targets for this optimizer.
    """

    targets = ForceBalanceOptimizer.get_registered_targets()

    assert len(targets) == 4
    assert all(issubclass(target, BaseTargetSchema) for target in targets.values())


def test_deregister_targets():
    """
    Test deregistering targets from optimizers.
    """

    class CustomOptimizer(BaseOptimizer):
        """A dummy optimizer class to use in tests."""

        @classmethod
        def name(cls):
            return "CustomOptimizer"

    assert len(CustomOptimizer.get_registered_targets()) == 0

    CustomOptimizer.register_target(TorsionProfileTargetSchema)

    assert len(CustomOptimizer.get_registered_targets()) == 1
    assert "torsionprofile" in CustomOptimizer.get_registered_targets()

    CustomOptimizer.deregister_target("TorsionProfile")
    assert len(CustomOptimizer.get_registered_targets()) == 0


def test_deregister_target_error():
    """
    Test deregistering targets from optimizers.
    """

    with pytest.raises(
        TargetRegisterError, match="No target with the name fake-target"
    ):
        ForceBalanceOptimizer.deregister_target("fake-target")


def test_register_target_existing_error():
    with pytest.raises(TargetRegisterError, match="has already been registered with"):
        ForceBalanceOptimizer.register_target(TorsionProfileTargetSchema)


def test_register_target_type_error():
    with pytest.raises(TargetRegisterError, match="does not inherit from the"):
        ForceBalanceOptimizer.register_target(float)


def test_validate_schema_bad_optimizer(general_optimization_schema):
    class CustomOptimizer(BaseOptimizer):
        """A dummy optimizer class to use in tests."""

        @classmethod
        def _schema_class(cls):
            return float

    with pytest.raises(OptimizerError, match="optimizer can only be used with"):
        CustomOptimizer._validate_schema(general_optimization_schema.stages[0])


def test_validate_schema_bad_target(general_optimization_schema):
    class CustomOptimizer(BaseOptimizer):
        """A dummy optimizer class to use in tests."""

        @classmethod
        def _schema_class(cls):
            return ForceBalanceSchema

    with pytest.raises(
        TargetRegisterError, match="target type is not registered with the"
    ):
        CustomOptimizer._validate_schema(general_optimization_schema.stages[0])


def test_prepare(general_optimization_schema, monkeypatch):
    class CustomOptimizer(BaseOptimizer):
        """A dummy optimizer class to use in tests."""

    validated = False
    prepared = False

    def on_validate(*args, **kwargs):
        nonlocal validated
        validated = True

    def on_prepared(*args, **kwargs):
        nonlocal prepared
        prepared = True

    monkeypatch.setattr(CustomOptimizer, "_validate_schema", on_validate)
    monkeypatch.setattr(CustomOptimizer, "_prepare", on_prepared)

    CustomOptimizer.prepare(
        general_optimization_schema.stages[0],
        ForceField(general_optimization_schema.initial_force_field),
        "",
    )

    assert validated
    assert prepared


def test_optimize(general_optimization_schema, monkeypatch):
    class CustomOptimizer(BaseOptimizer):
        """A dummy optimizer class to use in tests."""

    prepared = False
    optimized = False

    def on_prepared(*args, **kwargs):
        nonlocal prepared
        prepared = True

    def on_optimize(*args, **kwargs):
        nonlocal optimized
        optimized = True

    monkeypatch.setattr(CustomOptimizer, "_optimize", on_optimize)
    monkeypatch.setattr(CustomOptimizer, "prepare", on_prepared)

    CustomOptimizer.optimize(
        general_optimization_schema.stages[0],
        ForceField(general_optimization_schema.initial_force_field),
    )

    assert optimized
    assert prepared
