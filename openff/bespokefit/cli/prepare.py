import json

import click
from click import ClickException
from pydantic import ValidationError

from openff.bespokefit.optimizers import get_optimizer
from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationSchema,
)

_SCHEMA_TYPES = {"general": OptimizationSchema, "bespoke": BespokeOptimizationSchema}


@click.command("prepare")
@click.option(
    "-i",
    "--input",
    "input_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="The file path to a JSON serialized optimization schema. This can be "
    "either a general or a bespoke schema.",
)
def prepare_cli(input_path):
    """Prepare an optimizations' input files based on its schema."""

    _general_error_text = "the input path did not point to a valid optimization schema"

    try:

        with open(input_path) as file:
            schema_contents = json.load(file)

    except json.JSONDecodeError:

        raise ClickException(
            f"{_general_error_text}\n\nThe contents could not be parsed as JSON."
        )

    schema_type_string = schema_contents.get("type", None)

    if schema_type_string is None:
        raise ClickException(
            f"{_general_error_text}\n\nThe optimization type was not specified by "
            f"the schema."
        )
    if schema_type_string not in _SCHEMA_TYPES:
        raise ClickException(
            f"{_general_error_text}\n\nThe optimization type ({schema_type_string}) "
            f"is not supported."
        )

    schema_type = _SCHEMA_TYPES[schema_type_string]

    try:
        schema: OptimizationSchema = schema_type.parse_file(input_path)
    except ValidationError as e:
        raise ClickException(f"{_general_error_text}\n\n({e})")

    optimizer = get_optimizer(schema.optimizer.type)
    optimizer.prepare(schema, "optimization-inputs" if schema.id is None else schema.id)
