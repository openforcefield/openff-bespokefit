""""""
import os
import shutil
import tempfile
from contextlib import contextmanager
from typing import Optional

from openff.bespokefit.executor.services import current_settings


@contextmanager
def temporary_cd(path: Optional[str] = None, cleanup: Optional[bool] = None):
    """Temporarily move the current working directory to the path specified.

    Parameters
    ----------
    path
        The path to CD into. If ``None`` or not specified, a temporary directory
        will be created.
    cleanup
        Whether the directory and its contents should be kept after the context
        manager exits. If ``True``, the temporary directory and its contents
        will be destroyed when the context manager exits; if ``False``, it will
        be kept. If ``None`` or not specified, the directory is destroyed if
        ``Path`` is not specified and the BEFLOW_KEEP_TMP_FILES setting is
        ``False``.
    Returns
    -------
    """
    if path is not None and len(path) == 0:
        yield
        return

    if path is None:
        path = tempfile.mkdtemp()
        cleanup = (
            (not current_settings().BEFLOW_KEEP_TMP_FILES)
            if cleanup is None
            else cleanup
        )
    else:
        cleanup = False if cleanup is None else cleanup

    old_directory = os.getcwd()

    try:
        os.chdir(path)
        yield

    finally:
        os.chdir(old_directory)
        if cleanup:
            shutil.rmtree(path)
