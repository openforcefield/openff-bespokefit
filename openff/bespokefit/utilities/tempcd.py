""""""
import os
import shutil
import tempfile
from contextlib import contextmanager
from typing import Optional

from openff.bespokefit.executor.services import current_settings


@contextmanager
def temporary_cd(path: Optional[str] = None):
    """Temporarily move the current working directory to the path specified.

    Parameters
    ----------
    path
        The path to CD into. If ``None`` or not specified, a temporary directory
        will be created.
    Returns
    -------
    """
    # If the target path is "", we just want the current working directory.
    if path is not None and len(path) == 0:
        yield
        return

    # If a path is not given, create a temporary directory
    if path is None:
        path = tempfile.mkdtemp(dir=".")
        print(f"created temporary directory {path}")
        cleanup = not current_settings().BEFLOW_KEEP_TMP_FILES
    else:
        cleanup = False

    old_directory = os.getcwd()

    try:
        os.chdir(path)
        yield

    finally:
        os.chdir(old_directory)
        # If we created a temporary directory, clean it up
        if cleanup:
            print(f"cleaning up temporary directory {path}")
            shutil.rmtree(path)
