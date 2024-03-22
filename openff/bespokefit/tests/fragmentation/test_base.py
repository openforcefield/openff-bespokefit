"""Test the fragmentation engine registration system."""
import abc

import pytest
from openff.fragmenter.fragment import Fragmenter, PfizerFragmenter, WBOFragmenter

from openff.bespokefit.exceptions import FragmenterError
from openff.bespokefit.fragmentation import (
    FragmentationEngine,
    deregister_fragmentation_engine,
    get_fragmentation_engine,
    list_fragmentation_engines,
    register_fragmentation_engine,
)


class MockEngine(Fragmenter, abc.ABC):
    """"""


def test_fragmentation_engine_type():
    assert {*FragmentationEngine.__args__} == {WBOFragmenter, PfizerFragmenter}


def test_list_fragmentation_engines():
    """Make sure all default fragmentation engines are listed."""

    available_engines = list_fragmentation_engines()

    assert "wbofragmenter" in available_engines
    assert "pfizerfragmenter" in available_engines


@pytest.mark.parametrize(
    "name, expected_type",
    [("WbOfRaGmEnTeR", WBOFragmenter), ("pfizerfragmenter", PfizerFragmenter)],
)
def test_get_fragmentation_engine(name, expected_type):
    """Make sure a fragmentation engine can be retrieved"""

    engine_type = get_fragmentation_engine(engine=name)
    assert engine_type == expected_type


def test_get_fragmentation_engine_error():
    """
    Make sure an error is raised if the fragmentation engine is not registered.
    """
    with pytest.raises(FragmenterError, match="was not registered with"):
        get_fragmentation_engine(engine="badengine")


def test_remove_missing_engine():
    """
    If we try to remove an engine that is not registered raise an error.
    """

    with pytest.raises(FragmenterError, match="was not registered with"):
        deregister_fragmentation_engine(engine="badengine")


@pytest.mark.parametrize("engine", [MockEngine, "MockEngine"])
def test_removing_engines(engine):
    """
    Make sure once an engine is removed it does not show as listed.
    """

    register_fragmentation_engine(MockEngine)
    assert "mockengine" in list_fragmentation_engines()

    deregister_fragmentation_engine(engine)
    assert "mockengine" not in list_fragmentation_engines()


def test_register_engines_invalid():
    """
    Try and register an invalid fragment engine.
    """

    with pytest.raises(FragmenterError, match="must be a subclass of"):
        register_fragmentation_engine(float)


def test_reregister_engine():
    """
    Make sure an error is raised if we re register an engine without using replace .
    """

    with pytest.raises(FragmenterError, match="is already registered"):
        register_fragmentation_engine(engine=WBOFragmenter, replace=False)

    register_fragmentation_engine(engine=WBOFragmenter, replace=True)
