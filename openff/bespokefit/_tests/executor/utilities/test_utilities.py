import pytest
import requests
import rich
from rich import pretty

from openff.bespokefit._tests import does_not_raise
from openff.bespokefit.executor.utilities import handle_common_errors
from openff.bespokefit.executor.utilities._utilities import ErrorState


def _raise(exception):
    raise exception


@pytest.mark.parametrize(
    "inner_func, expected_text, expected_state, expected_raises",
    [
        (
            lambda: rich.get_console().print("general output"),
            "general output",
            ErrorState(has_errored=False),
            does_not_raise(),
        ),
        (
            lambda: _raise(requests.HTTPError()),
            "an internal HTTP error occured",
            ErrorState(has_errored=True),
            does_not_raise(),
        ),
        (
            lambda: _raise(requests.ConnectionError()),
            "failed to connect to the bespoke executor",
            ErrorState(has_errored=True),
            does_not_raise(),
        ),
        (
            lambda: _raise(KeyboardInterrupt),
            "",
            ErrorState(has_errored=True),
            does_not_raise(),
        ),
        (
            lambda: _raise(ValueError("general error")),
            "",
            ErrorState(has_errored=None),
            pytest.raises(ValueError, match="general error"),
        ),
    ],
)
def test_handle_common_errors(
    inner_func,
    expected_text,
    expected_state,
    expected_raises,
):
    console = rich.get_console()
    pretty.install(console)

    with expected_raises:
        with console.capture() as capture:
            with handle_common_errors(console) as error_state:
                inner_func()

    assert expected_text in capture.get()
    assert expected_state == error_state
