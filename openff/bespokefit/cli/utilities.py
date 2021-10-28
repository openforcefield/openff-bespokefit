from typing import TYPE_CHECKING, Callable, List

import click

if TYPE_CHECKING:
    import rich


def print_header(console: "rich.Console"):

    console.line()
    console.rule("OpenFF Bespoke")
    console.line()


def create_command(
    click_command: click.command, click_options: List[click.option], func: Callable
):
    """Programmatically apply click options to a function."""

    for option in reversed(click_options):
        func = option(func)

    return click_command(func)
