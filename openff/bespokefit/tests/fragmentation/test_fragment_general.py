"""
Test the base and general methods of fragmentation.
"""

import pytest

from openff.bespokefit.exceptions import FragmenterError
from openff.bespokefit.fragmentation import (
    WBOFragmenter,
    deregister_fragment_engine,
    get_fragmentation_engine,
    list_fragment_engines,
    register_fragment_engine,
)


def test_list_fragmentation_engines():
    """
    Make sure all default fragmentation engines are listed.
    """
    engines = list_fragment_engines()
    assert WBOFragmenter().type.lower() in engines


@pytest.mark.parametrize(
    "settings",
    [
        pytest.param(("WBOFragmenter", {"wbo_threshold": 1}), id="WBO thresh 1"),
        pytest.param(
            (
                "WBOFragmenter",
                {"wbo_threshold": 0.2, "keep_non_rotor_ring_substituents": False},
            ),
            id="WBO thresh 0.2, False",
        ),
    ],
)
def test_get_fragmentation_engine_settings(settings):
    """
    Make sure a fragmentation engine can be build by passing the name and some settings.
    """
    name, extras = settings
    engine = get_fragmentation_engine(fragmentation_engine=name, **extras)
    assert engine.type == name
    for att, value in extras.items():
        assert getattr(engine, att) == value


def test_get_fragmentation_engine_no_settings():
    """
    If no settings are provided make sure the engine is returned with defaults.
    """
    engine = get_fragmentation_engine(fragmentation_engine="WBOFragmenter")
    assert engine.wbo_threshold == engine.__fields__["wbo_threshold"].default
    assert (
        engine.keep_non_rotor_ring_substituents
        == engine.__fields__["keep_non_rotor_ring_substituents"].default
    )


def test_get_fragmentation_engine_error():
    """
    Make sure an error is raised if the fragmentation engine is not registered.
    """
    with pytest.raises(FragmenterError):
        _ = get_fragmentation_engine(fragmentation_engine="badengine")


def test_remove_missing_engine():
    """
    If we try to remove an engine that is not registered raise an error.
    """

    with pytest.raises(FragmenterError):
        deregister_fragment_engine(fragment_engine="badengine")


def test_removing_engines():
    """
    Make sure once an engine is removed it does not show as listed.
    """
    engine = WBOFragmenter()
    assert engine.type.lower() in list_fragment_engines()
    # now remove
    deregister_fragment_engine(fragment_engine=engine)
    assert engine.type.lower() not in list_fragment_engines()

    # now add back to not spoil tests
    register_fragment_engine(fragment_engine=engine)


def test_register_engines_invalid():
    """
    Try and register an invalid fragment engine.
    """

    with pytest.raises(FragmenterError):
        register_fragment_engine(float)


def test_reregister_engine():
    """
    Make sure an error is raised if we re register an engine without using replace .
    """
    engine = WBOFragmenter()
    # try and add again
    with pytest.raises(FragmenterError):
        register_fragment_engine(fragment_engine=engine, replace=False)

    # now try with replace true
    register_fragment_engine(fragment_engine=engine, replace=True)
