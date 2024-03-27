"""Miscellaneous CLI utilities."""

from collections.abc import Callable
from typing import Any

import click
from click.exceptions import Exit
from rich.console import Console


def print_header(console: Console):
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


def exit_with_messages(*messages: Any, console: Console, exit_code: int = 0):
    """Exit with provided error messages."""
    console.print(*messages)
    raise Exit(code=exit_code)
