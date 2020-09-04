"""
BespokeFit
Creating bespoke parameters for individual molecules.
"""

# Handle versioneer
from ._version import get_versions
from .bespokefit import *

versions = get_versions()
__version__ = versions["version"]
__git_revision__ = versions["full-revisionid"]
del get_versions, versions
