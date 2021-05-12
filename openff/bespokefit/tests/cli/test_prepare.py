import pytest

from openff.bespokefit.cli.prepare import prepare_cli
from openff.bespokefit.optimizers import ForceBalanceOptimizer


@pytest.mark.parametrize(
    "schema_contents, expected_match",
    [
        ("abc", "The contents could not be parsed as JSON."),
        ("{}", "The optimization type was not specified"),
        ('{"type": "abc"}', "The optimization type (abc) is not supported"),
        ('{"type": "general"}', "4 validation errors for"),
    ],
)
def test_prepare_errors(runner, schema_contents, expected_match):

    with open("input.json", "w") as file:
        file.write(schema_contents)

    arguments = ["-i", "input.json"]

    result = runner.invoke(prepare_cli, arguments)
    assert result.exit_code != 0

    assert expected_match in result.output
    assert "the input path did not point to a valid optimization" in result.output


def test_prepare(runner, bespoke_optimization_schema, monkeypatch):

    monkeypatch.setattr(ForceBalanceOptimizer, "prepare", lambda *args, **kwargs: None)

    with open("input.json", "w") as file:
        file.write(bespoke_optimization_schema.json())

    arguments = ["-i", "input.json"]

    result = runner.invoke(prepare_cli, arguments)

    if result.exit_code != 0:
        raise result.exception
