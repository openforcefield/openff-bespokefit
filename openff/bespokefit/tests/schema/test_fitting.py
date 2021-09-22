"""
Test all parts of the fitting schema.
"""

from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationSchema,
)


def test_n_targets(general_optimization_schema):
    expected_n_targets = len(general_optimization_schema.targets)
    assert general_optimization_schema.n_targets == expected_n_targets


def test_general_fitting_force_field(general_optimization_schema):

    target_parameter = general_optimization_schema.parameters[0]

    force_field = general_optimization_schema.get_fitting_force_field()

    parameter_handler = force_field.get_parameter_handler(target_parameter.type)
    parameter = parameter_handler.parameters[target_parameter.smirks]

    assert parameter.attribute_is_cosmetic("parameterize")
    assert parameter._parameterize == "k1"


def test_bespoke_fitting_force_field(bespoke_optimization_schema):

    force_field = bespoke_optimization_schema.get_fitting_force_field()
    assert "parameterize" in force_field.to_string()


def test_general_schema_export_roundtrip(general_optimization_schema):
    """
    Make sure that the fitting schema can be exported and imported.
    """
    OptimizationSchema.parse_raw(general_optimization_schema.json())


def test_bespoke_schema_export_roundtrip(bespoke_optimization_schema):
    """
    Make sure that the fitting schema can be exported and imported.
    """
    BespokeOptimizationSchema.parse_raw(bespoke_optimization_schema.json())
