import click
import pytest
import rich
from click.exceptions import Exit

from openff.bespokefit.cli.utilities import (
    create_command,
    exit_with_messages,
    print_header,
)


def test_print_header():
    console = rich.get_console()

    with console.capture() as capture:
        print_header(console)

    assert "OpenFF Bespoke" in capture.get()


def test_create_command(runner):
    mock_command = create_command(
        click_command=click.command(name="test-command"),
        click_options=[
            click.option("--option-2", type=click.STRING),
            click.option("--option-1", type=click.STRING),
        ],
        func=lambda option_1, option_2: None,
    )

    help_output = runner.invoke(mock_command, ["--help"])
    assert help_output.exit_code == 0

    assert "option-1" in help_output.output
    assert "option-2" in help_output.output

    # Options should be appear in the specified order
    assert help_output.output.index("option-2") < help_output.output.index("option-1")


def test_exit_with_messages():
    console = rich.get_console()

    with console.capture() as capture:
        with pytest.raises(Exit) as raises:
            exit_with_messages(
                "general message 1",
                "general message 2",
                console=console,
                exit_code=2,
            )

    assert raises.value.exit_code == 2

    assert "general message 1" in capture.get()
    assert "general message 2" in capture.get()
