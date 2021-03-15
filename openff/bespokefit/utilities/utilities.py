import errno
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional, Union

from openff.qcsubmit.common_structures import MoleculeAttributes
from openff.qcsubmit.factories import BasicDatasetFactory
from openforcefield.topology import Molecule


def get_data_file_path(relative_path: str) -> str:
    """Get the full path to one of the files in the data directory.

    Parameters
    ----------
    relative_path : str
        The relative path of the file to load.

    Returns
    -------
        The absolute path to the file.

    Raises
    ------
    FileNotFoundError
    """

    from pkg_resources import resource_filename

    file_path = resource_filename(
        "openff.bespokefit", os.path.join("data", relative_path)
    )

    if not os.path.exists(file_path):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), file_path)

    return file_path


@contextmanager
def temporary_cd(directory_path: Optional[Union[str, Path]] = None):
    """Temporarily move the current working directory to the path
    specified. If no path is given, a temporary directory will be
    created, moved into, and then destroyed when the context manager
    is closed.

    Parameters
    ----------
    directory_path

    Returns
    -------

    """

    directory_path = str(directory_path)

    if directory_path is not None and len(directory_path) == 0:
        yield
        return

    old_directory = os.getcwd()

    try:

        if directory_path is None:

            with TemporaryDirectory() as new_directory:
                os.chdir(new_directory)
                yield

        else:

            os.chdir(directory_path)
            yield

    finally:
        os.chdir(old_directory)


def safe_rmdir(directory_path: Union[str, Path]):
    shutil.rmtree(directory_path, ignore_errors=True)


def get_molecule_cmiles(molecule: Molecule) -> MoleculeAttributes:
    """
    Generate the molecule cmiles data.
    """
    factory = BasicDatasetFactory()
    return factory.create_cmiles_metadata(molecule)
