import pytest
from openff.toolkit.typing.engines.smirnoff import ForceField
from simtk import unit

from openff.bespokefit.schema.results import BespokeOptimizationResults


@pytest.fixture()
def bespoke_optimization_results(
    bespoke_optimization_schema,
) -> BespokeOptimizationResults:

    force_field = ForceField(bespoke_optimization_schema.initial_force_field)

    for key, value in bespoke_optimization_schema.initial_parameter_values.items():

        for attribute in key.attributes:

            expected_unit = getattr(
                force_field[key.type].parameters[key.smirks], attribute
            ).unit

            setattr(
                force_field[key.type].parameters[key.smirks],
                attribute,
                2 * expected_unit,
            )

    return BespokeOptimizationResults(
        input_schema=bespoke_optimization_schema,
        provenance={},
        status="success",
        refit_force_field=force_field.to_string(),
    )


def test_initial_parameter_values(bespoke_optimization_results):

    parameter_values = bespoke_optimization_results.initial_parameter_values

    assert len(parameter_values) == len(
        bespoke_optimization_results.input_schema.parameters
    )
    assert all(isinstance(x, unit.Quantity) for x in parameter_values.values())

    assert all(x != 2 * unit.kilojoules_per_mole for x in parameter_values.values())


def test_refit_parameter_values(bespoke_optimization_results):

    refit_parameter_values = bespoke_optimization_results.refit_parameter_values

    assert len(refit_parameter_values) == len(
        bespoke_optimization_results.input_schema.parameters
    )
    assert all(isinstance(x, unit.Quantity) for x in refit_parameter_values.values())

    assert all(
        x == 2 * unit.kilocalories_per_mole for x in refit_parameter_values.values()
    )
