from contextlib import contextmanager

# A workaround for segfaults when using OE on GHA...
try:
    from openeye import oechem

    if oechem.OEChemIsLicensed():

        oechem.OESetMemPoolMode(
            oechem.OEMemPoolMode_Mutexed | oechem.OEMemPoolMode_UnboundedCache
        )

except (ImportError, ModuleNotFoundError):
    pass


@contextmanager
def does_not_raise():
    """A helpful context manager to use inplace of a pytest raise statement
    when no exception is expected."""
    yield
