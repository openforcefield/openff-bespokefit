import functools
import re
import subprocess
from typing import Dict, Optional

import pkg_resources


@functools.lru_cache()
def _get_conda_list_package_versions() -> Dict[str, str]:
    """Returns the versions of any packages found while executing `conda list`."""

    list_output = subprocess.check_output(["conda", "list"]).decode().split("\n")

    package_versions = {}

    for output_line in list_output[3:-1]:

        package_name, package_version, *_ = re.split(" +", output_line)
        package_versions[package_name] = package_version

    return package_versions


def get_ambertools_version() -> Optional[str]:
    """Attempts to retrieve the version of the currently installed AmberTools."""

    try:
        distribution = pkg_resources.get_distribution("AmberTools")
        return distribution.version

    except pkg_resources.DistributionNotFound:
        return _get_conda_list_package_versions().get("ambertools", None)


def get_openeye_versions() -> Dict[str, str]:
    """Attempts to retrieve the versions of the available (and licensed) OpenEye
    toolkits commonly used by this package and its key dependencies."""

    versions = {}

    try:
        import openeye
        from openeye import oechem, oeomega, oequacpac

        if oechem.OEChemIsLicensed():
            versions["openeye.oechem"] = openeye.__version__
        if oequacpac.OEQuacPacIsLicensed():
            versions["openeye.oequacpac"] = openeye.__version__
        if oeomega.OEOmega():
            versions["openeye.oeomega"] = openeye.__version__

    except (ImportError, ModuleNotFoundError):
        pass

    return versions
