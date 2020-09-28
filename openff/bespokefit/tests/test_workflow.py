"""
Test for the bespoke-fit workflow generator.
"""

import pytest

from ..exceptions import ForceFieldError
from ..workflow import WorkflowFactory


@pytest.mark.parametrize("forcefield", [
    pytest.param(("openff-1.0.0.offxml", None), id="Parsley 1.0.0"),
    pytest.param(("bespoke.offxml", ForceFieldError), id="Local forcefield"),
    pytest.param(("smirnoff99Frosst-1.0.7.offxml", None), id="Smirnoff99Frosst installed")
])
def test_workflow_forcefield_setter(forcefield):
    """
    Make sure we only accept forcefields that have been installed.
    """
    force_file, error = forcefield
    factory = WorkflowFactory()
    if error is None:
        factory.initial_forcefield = force_file
    else:
        with pytest.raises(ForceFieldError):
            factory.initial_forcefield = force_file
