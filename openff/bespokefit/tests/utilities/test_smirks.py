import pytest

from openff.bespokefit.tests import does_not_raise
from openff.bespokefit.utilities.smirks import compare_smirks_graphs, validate_smirks


@pytest.mark.parametrize(
    "smirks1, smirks2, expected",
    [
        ("[#6:1]-[#6:2]", "[#6:1]-[#6:2]", True),
        ("[#6:1]-[#6:2]", "[#6:1]-[#1:2]", False),
    ],
)
def test_compare_smirks_graphs(smirks1, smirks2, expected):

    assert compare_smirks_graphs(smirks1, smirks2) == expected


@pytest.mark.parametrize(
    "smirks, n_tags, expected_raises",
    [
        ("[#6:1]", 1, does_not_raise()),
        ("[#6:1]-[#6:2]", 1, pytest.raises(AssertionError)),
    ],
)
def test_validate_smirks(smirks, n_tags, expected_raises):

    with expected_raises:
        validate_smirks(smirks, n_tags)
