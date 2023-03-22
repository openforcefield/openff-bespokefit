""""""
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Union

from openff.bespokefit.executor.services import current_settings


@contextmanager
def temporary_cd(path: Optional[Union[str, Path]] = None):
    """
    Context manager to move the current working directory to the path specified.

    If no path is given or the path does not exist, a temporary directory will
    be created. This temporary directory and its contents will be deleted when
    the context manager exits.

    Parameters
    ----------
    path
        The path to CD into. If ``None`` or not specified, a temporary directory
        will be created. If specified but the path does not exist, a temporary
        directory with that name will be created.
    """
    # Normalize path to a pathlib Path
    path: Optional[Path] = None if path is None else Path(path)

    # Decide whether to clean up based on bespokefit settings
    cleanup = not current_settings().BEFLOW_KEEP_TMP_FILES

    # If a path is not given, create a temporary directory
    if path is None:
        path = Path(tempfile.mkdtemp(dir="."))
    # If a path is given but does not already exist, create it
    elif not path.exists():
        path.mkdir(parents=True)
    # If we didn't create the path, do NOT clean it up
    else:
        cleanup = False

    old_directory = os.getcwd()

    try:
        os.chdir(path)
        yield

    finally:
        os.chdir(old_directory)
        # If we created the directory, clean it up
        if cleanup:
            print(f"cleaning up temporary directory {path}")
            shutil.rmtree(path)
