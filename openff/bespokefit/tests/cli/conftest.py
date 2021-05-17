import pytest
from click.testing import CliRunner


@pytest.fixture(scope="module")
def runner() -> CliRunner:
    """Creates a new click CLI runner object."""
    click_runner = CliRunner()

    with click_runner.isolated_filesystem():
        yield click_runner
