"""
BespokeFit: Creating bespoke parameters for individual molecules.
"""

import logging
import sys

from ._version import get_versions

versions = get_versions()
__version__ = versions["version"]
__git_revision__ = versions["full-revisionid"]
del get_versions, versions


# Silence verbose messages when running the CLI otherwise you can't read the output
# without seeing tens of 'Unable to load AmberTools' or don't import simtk warnings...
if sys.argv[0].endswith("openff-bespoke"):
    from openff.bespokefit.utilities.logging import DeprecationWarningFilter

    # if "openff-bespoke"
    logging.getLogger("openff.toolkit").setLevel(logging.ERROR)
    logging.getLogger().addFilter(DeprecationWarningFilter())
