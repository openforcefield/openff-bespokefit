from contextlib import contextmanager


@contextmanager
def does_not_raise():
    """A helpful context manager to use inplace of a pytest raise statement
    when no exception is expected."""
    yield
