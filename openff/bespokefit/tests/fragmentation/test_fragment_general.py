"""
Test the base and general methods of fragmentation.
"""
import os

import pytest
from openforcefield.topology import Molecule

from openff.bespokefit.exceptions import FragmenterError
from openff.bespokefit.fragmentation import (
    FragmentEngine,
    WBOFragmenter,
    deregister_fragment_engine,
    get_fragmentation_engine,
    list_fragment_engines,
    register_fragment_engine,
)
from openff.bespokefit.utilities import get_data_file_path


def test_list_fragmentation_engines():
    """
    Make sure all default fragmentation engines are listed.
    """
    engines = list_fragment_engines()
    assert WBOFragmenter().fragmentation_engine.lower() in engines


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
    assert engine.fragmentation_engine == name
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
    assert engine.fragmentation_engine.lower() in list_fragment_engines()
    # now remove
    deregister_fragment_engine(fragment_engine=engine)
    assert engine.fragmentation_engine.lower() not in list_fragment_engines()

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


@pytest.mark.parametrize(
    "molecules",
    [
        pytest.param(
            (
                "bace_parent.sdf",
                "bace_parent.sdf",
                {
                    0: 0,
                    1: 1,
                    2: 2,
                    3: 3,
                    4: 4,
                    5: 5,
                    6: 6,
                    7: 7,
                    8: 8,
                    9: 9,
                    10: 10,
                    11: 11,
                    12: 12,
                    13: 13,
                    14: 14,
                    15: 15,
                    16: 16,
                    17: 17,
                    18: 18,
                    19: 19,
                    20: 20,
                    21: 21,
                    22: 22,
                    23: 23,
                    24: 24,
                    25: 25,
                    26: 26,
                    27: 27,
                    28: 28,
                    29: 48,
                    30: 30,
                    31: 31,
                    32: 32,
                    33: 33,
                    34: 34,
                    35: 35,
                    36: 36,
                    37: 37,
                    38: 38,
                    39: 39,
                    40: 40,
                    41: 41,
                    42: 42,
                    43: 43,
                    44: 44,
                    45: 45,
                    46: 46,
                    47: 47,
                    48: 29,
                },
            ),
            id="Same molecule",
        ),
        pytest.param(
            (
                "bace_parent.sdf",
                "bace_frag1.sdf",
                {
                    0: 7,
                    2: 8,
                    6: 9,
                    10: 10,
                    7: 18,
                    3: 6,
                    19: 38,
                    11: 11,
                    8: 17,
                    4: 15,
                    1: 14,
                    5: 13,
                    9: 12,
                    21: 34,
                    17: 35,
                    13: 36,
                    20: 37,
                    18: 33,
                    14: 32,
                    12: 31,
                },
            ),
            id="BACE parent fragment1 mapping",
        ),
        pytest.param(
            (
                "bace_parent.sdf",
                "bace_frag2.sdf",
                {
                    0: 9,
                    1: 8,
                    3: 7,
                    5: 6,
                    4: 18,
                    2: 10,
                    22: 38,
                    13: 5,
                    7: 24,
                    15: 1,
                    6: 2,
                    16: 4,
                    36: 30,
                    14: 0,
                    33: 26,
                    34: 27,
                    35: 28,
                    17: 25,
                    12: 19,
                    10: 20,
                    8: 21,
                    9: 22,
                    11: 23,
                    30: 46,
                    31: 47,
                    26: 44,
                    27: 45,
                    24: 42,
                    25: 43,
                    28: 40,
                    29: 41,
                    32: 39,
                    21: 31,
                    19: 32,
                    18: 33,
                },
            ),
            id="BACE parent fragment2 mapping",
        ),
    ],
)
def test_parent_fragment_mapping(molecules):
    """
    Test generating a parent fragment mapping.
    """

    pytest.skip("seg faults")

    molecule1, molecule2, atom_map = molecules
    mol1 = Molecule.from_file(
        get_data_file_path(os.path.join("test", "molecules", "bace", molecule1)), "sdf"
    )
    mol2 = Molecule.from_file(
        get_data_file_path(os.path.join("test", "molecules", "bace", molecule2)), "sdf"
    )
    mapping = FragmentEngine._get_fragment_parent_mapping(fragment=mol2, parent=mol1)
    assert mapping == atom_map
