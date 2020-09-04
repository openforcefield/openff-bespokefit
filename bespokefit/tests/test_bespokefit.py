"""
Unit and regression test for the bespokefit package.
"""

import sys

import pytest

# Import package, test suite, and other packages as needed
import bespokefit


def test_bespokefit_imported():
    """Sample test, will always pass so long as import statement worked"""
    assert "bespokefit" in sys.modules
