"""
Unit test ability to add and remove new optimizers as well as the various optimizer classes.
"""

import pytest

from openff.bespokefit.exceptions import OptimizerError, TargetRegisterError
from openff.bespokefit.optimizers import ForceBalanceOptimizer
from openff.bespokefit.optimizers.base import (
    deregister_optimizer,
    get_optimizer,
    list_optimizers,
    register_optimizer,
)
from openff.bespokefit.targets.torsions import (
    AbInitio_SMIRNOFF,
    TorsionDrive1D,
    TorsionProfile_SMIRNOFF,
)


def test_list_optimizers():
    """
    Make sure all registered optimizers are returned
    """

    # get optimizers in lower case
    optimizers = list_optimizers()
    assert "forcebalanceoptimizer" in optimizers


@pytest.mark.parametrize("optimizer_settings", [
    pytest.param(("ForceBalanceOptimizer", {"penalty_type": "L1", "job_type": "single", "convergence_step_criteria": 20}, None), id="Forcebalance normal settings"),
    pytest.param(("ForceBalanceOptimizer", {"extras": {"print_hessian": None}}, None), id="Forcebalanace extras"),
    pytest.param(("FancyOptimizer", {"optimzer": "fast"}, OptimizerError), id="Error missing optimizer")
])
def test_get_optimizer_with_settings(optimizer_settings):
    """
    Test getting optimizers with different settings.
    The settings should be auto applied to the optimizer.
    """
    optimzer_name, settings, error = optimizer_settings
    if error is None:
        optimizer = get_optimizer(optimizer_name=optimzer_name, **settings)
        for key, value in settings.items():
            assert getattr(optimizer, key) == value

    else:
        with pytest.raises(error):
            _ = get_optimizer(optimizer_name=optimzer_name, **settings)


def test_get_optimizer_no_settings():
    """
    Test getting an optimizer with no extra settings.
    """
    optimizer = get_optimizer(optimizer_name="ForceBalanceOptimizer")
    # make sure the settings are the default
    assert optimizer.dict() == ForceBalanceOptimizer().dict()


@pytest.mark.parametrize("optimizers", [
    pytest.param(("ForceBalanceOptimizer", None), id="Forcebalance by name"),
    pytest.param((ForceBalanceOptimizer(), None), id="Forcebalance by class"),
    pytest.param(("FancyOptimizer", OptimizerError), id="Missing optimizer")
])
def test_deregister_optimizers(optimizers):
    """
    Test removing optimizers from the registered list.
    """
    optimizer, error = optimizers
    if error is None:
        deregister_optimizer(optimizer=optimizer)
        # make sure it is missing
        assert "forcebalanceoptimizer" not in list_optimizers()
        # now add it back
        register_optimizer(ForceBalanceOptimizer())

    else:
        with pytest.raises(error):
            deregister_optimizer(optimizer=optimizer)


@pytest.mark.parametrize("optimizers", [
    pytest.param((ForceBalanceOptimizer(), False, OptimizerError), id="Forcebalance already registered"),
    pytest.param((ForceBalanceOptimizer(), True, None), id="Forcebalance replace"),
    pytest.param(({"optimizer_name": "forcebalance"}, False, OptimizerError), id="Dict error")
])
def test_register_optimizers(optimizers):
    """
    Test registering new optimizers to bespokefit.
    """
    optimizer, replace, error = optimizers
    if error is None:
        register_optimizer(optimizer=optimizer, replace=replace)

    else:
        with pytest.raises(error):
            register_optimizer(optimizer=optimizer, replace=replace)


def test_optimizer_name_validation():
    """
    Test that tring to reset the optimizer name does not work.
    """
    fb = ForceBalanceOptimizer(optimizer_name="testoptimizer")
    assert fb.optimizer_name == "ForceBalanceOptimizer"


@pytest.mark.parametrize("opt_target", [
    pytest.param((ForceBalanceOptimizer, "TorsionProfile_SMIRNOFF", {"fragmentation": False, "grid_spacings": [30]}, None), id="Torsionprofile with settings"),
    pytest.param((ForceBalanceOptimizer, "AbInitio_SMIRNOFF", {"weight": 2, "fragmentation": False}, None), id="AbInitio_SMIRNOFF with settings"),
    pytest.param((ForceBalanceOptimizer, "DDEC6_CHARGES", {}, TargetRegisterError), id="Missing targte error")
])
def test_get_optimization_target_settings(opt_target):
    """
    Test getting a registered optimization target from the optimizer with settings.
    """
    optimizer_class, target_name, settings, error = opt_target
    optimizer = optimizer_class()
    if error is None:
        target = optimizer.get_optimization_target(target_name=target_name, **settings)
        for key, value in settings.items():
            assert getattr(target, key) == value
    else:
        with pytest.raises(error):
            _ = optimizer.get_optimization_target(target_name=target_name)


@pytest.mark.parametrize("opt_target", [
    pytest.param((ForceBalanceOptimizer, AbInitio_SMIRNOFF), id="AbInitio_SMIRNOFF"),
    pytest.param((ForceBalanceOptimizer, TorsionProfile_SMIRNOFF), id="TorsionProfile_SMIRNOFF")
])
def test_get_optimization_target_no_settings(opt_target):
    """
    Test getting an optimization target with no new settings.
    """
    optimizer_class, target_class = opt_target
    optimizer = optimizer_class()
    target = target_class()
    # get the new target
    new_target = optimizer.get_optimization_target(target_name=target.name)
    assert new_target.dict() == target.dict()


@pytest.mark.parametrize("opt_target", [
    pytest.param((ForceBalanceOptimizer, "AbInitio_SMIRNOFF", {"fragmentation": False}, None), id="AbInitio_SMIRNOFF with settings"),
    pytest.param((ForceBalanceOptimizer, TorsionProfile_SMIRNOFF(), {}, None),
                 id="TorsionProfile_SMIRNOFF with settings"),
    pytest.param((ForceBalanceOptimizer, TorsionDrive1D(), {}, TargetRegisterError), id="Torsiondrive1D error.")
])
def test_set_optimization_targets_settings(opt_target):
    """
    Test the api for adding optimization targets to be executed in a workflow. Note targets must have been registered to be added.
    """
    optimizer_class, target, settings, error = opt_target
    optimizer = optimizer_class()
    if error is None:
        optimizer.set_optimization_target(target=target, **settings)
        assert len(optimizer.optimization_targets) == 1
        optimizer.clear_optimization_targets()

    else:
        with pytest.raises(error):
            optimizer.set_optimization_target(target=target, **settings)


def test_get_registered_targets():
    """
    Test listing all of the registered targets for this optimizer.
    """
    fb = ForceBalanceOptimizer()
    targets = fb.get_registered_targets()
    assert targets == [AbInitio_SMIRNOFF(), TorsionProfile_SMIRNOFF()]


@pytest.mark.parametrize("opt_targets", [
    pytest.param((ForceBalanceOptimizer, AbInitio_SMIRNOFF, None), id="Forcebalance and AbInitio_SMIRNOFF"),
    pytest.param((ForceBalanceOptimizer, TorsionDrive1D, TargetRegisterError), id="Forcebalance missing target")
])
def test_deregister_targets(opt_targets):
    """
    Test deregistering targets from optimizers.
    """
    optimizer_class, target_class, error = opt_targets
    optimizer = optimizer_class()
    target = target_class()

    if error is None:
        optimizer.deregister_target(target.name)
        assert target not in optimizer.get_registered_targets()
        # now add it back in
        optimizer.register_target(target)

    else:
        with pytest.raises(error):
            optimizer.deregister_target(target.name)


def test_register_optimization_target():
    """
    Test adding new optimization targets via the api.
    """
    fb = ForceBalanceOptimizer()
    # first try and add a target again with different settings
    target = TorsionProfile_SMIRNOFF(fragmentation=False, keywords={"test": True})
    with pytest.raises(TargetRegisterError):
        # this will not allow the target to be registered
        fb.register_target(target=target, replace=False)

    opt_target = fb.get_optimization_target(target_name=target.name)
    assert opt_target.fragmentation is True

    # now use the replace flag
    fb.register_target(target=target, replace=True)
    opt_target = fb.get_optimization_target(target_name=target.name)
    assert opt_target.fragmentation is False
    assert opt_target.keywords["test"] is True

    # now add a totally new target
    target = TorsionDrive1D()
    fb.register_target(target=target, replace=False)
    assert target in fb.get_registered_targets()
