from simtk import unit


def test_initial_parameter_values(bespoke_optimization_results):

    parameter_values = bespoke_optimization_results.initial_parameter_values

    assert len(parameter_values) == len(
        bespoke_optimization_results.input_schema.stages[0].parameters
    )
    assert all(
        isinstance(y, unit.Quantity)
        for x in parameter_values.values()
        for y in x.values()
    )

    assert all(
        y != 2 * unit.kilojoules_per_mole
        for x in parameter_values.values()
        for y in x.values()
    )


def test_refit_parameter_values(bespoke_optimization_results):

    refit_parameter_values = bespoke_optimization_results.refit_parameter_values

    assert len(refit_parameter_values) == len(
        bespoke_optimization_results.input_schema.stages[0].parameters
    )
    assert all(
        isinstance(y, unit.Quantity)
        for x in refit_parameter_values.values()
        for y in x.values()
    )

    assert all(
        y == 2 * unit.kilocalories_per_mole
        for x in refit_parameter_values.values()
        for y in x.values()
    )
