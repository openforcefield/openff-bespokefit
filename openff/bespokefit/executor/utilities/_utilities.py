"""Error handling in exeuctor."""

from contextlib import contextmanager
from typing import Optional

import requests
import rich
from typing_extensions import TypedDict

_FAILED_TO_CONNECT = (
    "[[red]ERROR[/red]] failed to connect to the bespoke executor - please make "
    "sure one is running and your connection settings are correct"
)


class ErrorState(TypedDict):
    """Whether or not this state has errorred."""

    has_errored: Optional[bool]


@contextmanager
def handle_common_errors(console: "rich.Console"):
    """
    Context manager that will capture common internal errors raised by a bespoke executor.

    Prints a useful error message to the console rather than a garbled traceback.

    The return value of the context manager can be queried to see if an error did actually occur.

    Parameters
    ----------
    console: rich.Console
        The rich console to print to.

    Returns
    -------
        A dictionary with keys of [``has_errored``, ].

    """
    error_state = ErrorState(has_errored=None)
    has_errored = True

    try:
        yield error_state
    except requests.HTTPError as e:
        message = (
            "an internal HTTP error occured"
            if e.response is None
            else f"{e.response.status_code} - {e.response.text}"
        )
        console.print(f"[[red]ERROR[/red]] {message}")
    except requests.ConnectionError:
        console.print(_FAILED_TO_CONNECT)
    except KeyboardInterrupt:
        pass
    else:
        has_errored = False

    error_state["has_errored"] = has_errored
