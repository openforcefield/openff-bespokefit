import pytest

from openff.bespokefit.cli.prepare import prepare_cli
from openff.bespokefit.optimizers import ForceBalanceOptimizer


@pytest.mark.parametrize(
    "schema_contents, force_field_path, expected_match",
    [
        (
            "abc",
            "openff-1.3.0.offxml",
            "the input path did not point to a valid optimization",
        ),
        ("", "fake-ff-path.offxml2", "error loading initial parameters"),
    ],
)
def test_prepare_errors(runner, schema_contents, force_field_path, expected_match):

    with open("input.json", "w") as file:
        file.write(schema_contents)

    arguments = ["-i", "input.json", "-ff", force_field_path]

    result = runner.invoke(prepare_cli, arguments)
    assert result.exit_code != 0

    assert expected_match in result.output


def test_prepare(runner, bespoke_optimization_schema, monkeypatch):

    monkeypatch.setattr(ForceBalanceOptimizer, "prepare", lambda *args, **kwargs: None)

    with open("input.json", "w") as file:
        file.write(bespoke_optimization_schema.stages[0].json())

    arguments = [
        "-i",
        "input.json",
        "-ff",
        bespoke_optimization_schema.initial_force_field,
    ]

    result = runner.invoke(prepare_cli, arguments)

    if result.exit_code != 0:
        raise result.exception
