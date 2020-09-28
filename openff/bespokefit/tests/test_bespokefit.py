"""
Unit and regression test for the bespokefit package.
"""

import sys

# Import package, test suite, and other packages as needed
from openff.bespokefit import bespokefit


def test_bespokefit_imported():
    """Sample test, will always pass so long as import statement worked"""
    assert "bespokefit" in sys.modules
