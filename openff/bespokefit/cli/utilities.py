"""Miscellaneous CLI utilities."""

from typing import TYPE_CHECKING, Any, Callable

import click
from click.exceptions import Exit

if TYPE_CHECKING:
    import rich


def print_header(console: "rich.Console"):
    """Print the header for all CLI commands."""
    console.line()
    console.rule("OpenFF Bespoke")
    console.line()


def create_command(
    click_command: click.command,
    click_options: list[click.option],
    func: Callable,
):
    """Programmatically apply click options to a function."""
    for option in reversed(click_options):
        func = option(func)

    return click_command(func)


def exit_with_messages(*messages: Any, console: "rich.Console", exit_code: int = 0):
    """Exit with provided error messages."""
    console.print(*messages)
    raise Exit(code=exit_code)
