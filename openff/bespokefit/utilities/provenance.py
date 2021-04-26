from typing import Dict, Optional

import pkg_resources


def get_ambertools_version() -> Optional[str]:
    """Attempts to retrieve the version of the currently installed AmberTools."""

    try:
        distribution = pkg_resources.get_distribution("AmberTools")
        return distribution.version
    except pkg_resources.DistributionNotFound:
        return None


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
