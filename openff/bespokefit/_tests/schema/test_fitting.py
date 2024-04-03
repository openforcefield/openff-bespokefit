"""
Test all parts of the fitting schema.
"""

from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationSchema,
)


def test_n_targets(general_optimization_schema):
    expected_n_targets = len(general_optimization_schema.stages[0].targets)
    assert general_optimization_schema.stages[0].n_targets == expected_n_targets


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
