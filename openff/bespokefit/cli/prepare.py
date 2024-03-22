"""Host of `prepare` option in CLI."""

import json

import click
from click import ClickException
from pydantic import ValidationError

from openff.bespokefit.optimizers import get_optimizer
from openff.bespokefit.schema.fitting import OptimizationStageSchema


@click.command("prepare")
@click.option(
    "-i",
    "--input",
    "input_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="The file path to a JSON serialized optimization **stage** schema.",
)
@click.option(
    "-ff",
    "--force-field",
    "initial_force_field_path",
    type=click.STRING,
    help="The file path to the starting force field.",
)
def prepare_cli(input_path, initial_force_field_path):
    """Prepare an optimizations' input files based on its schema."""
    from openff.toolkit.typing.engines.smirnoff import ForceField

    _general_error_text = "the input path did not point to a valid optimization schema"

    try:
        initial_force_field = ForceField(initial_force_field_path)
    except BaseException as e:
        raise ClickException(f"error loading initial parameters\n\n({e})")

    try:
        schema: OptimizationStageSchema = OptimizationStageSchema.parse_file(input_path)
    except (ValidationError, json.JSONDecodeError) as e:
        raise ClickException(f"{_general_error_text}\n\n({e})")

    optimizer = get_optimizer(schema.optimizer.type)
    optimizer.prepare(schema, initial_force_field, "optimization-inputs")
