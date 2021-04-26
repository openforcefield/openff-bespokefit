import importlib

import pytest

from openff.bespokefit.utilities.provenance import (
    get_ambertools_version,
    get_openeye_versions,
)


def test_get_ambertools_version_found():

    # Skip if ambertools is not installed.
    pytest.importorskip("parmed")

    assert get_ambertools_version() is not None


def test_get_ambertools_version_not_found():

    try:
        importlib.import_module("parmed")
    except ImportError:
        assert get_ambertools_version() is None
        return

    pytest.skip("only run when ambertools is not installed.")


def test_get_openeye_versions():
    # Skip if ambertools is not installed.
    pytest.importorskip("openeye")
    assert len(get_openeye_versions()) > 0


def test_get_openeye_versions_not_found():

    try:
        importlib.import_module("openeye")
    except ImportError:
        assert len(get_openeye_versions()) == 0
        return

    pytest.skip("only run when openeye is not installed.")
