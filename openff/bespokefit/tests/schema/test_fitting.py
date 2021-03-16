"""
Test all parts of the fitting schema.
"""
import os

from openff.qcsubmit.datasets import TorsiondriveDataset
from openff.qcsubmit.results import TorsionDriveCollectionResult

from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationSchema,
)
from openff.bespokefit.utilities import get_data_file_path


def test_n_targets(general_optimization_schema):
    expected_n_targets = len(general_optimization_schema.targets)
    assert general_optimization_schema.n_targets == expected_n_targets


def test_general_fitting_force_field(general_optimization_schema):

    target_parameter = general_optimization_schema.target_parameters[0]

    force_field = general_optimization_schema.get_fitting_force_field()

    parameter_handler = force_field.get_parameter_handler(target_parameter.type)
    parameter = parameter_handler.parameters[target_parameter.smirks]

    assert parameter.attribute_is_cosmetic("parameterize")
    assert parameter._parameterize == "k1"


def test_bespoke_n_tasks(bespoke_optimization_schema):
    assert bespoke_optimization_schema.n_tasks == 1


def test_bespoke_task_hashes(bespoke_optimization_schema):

    assert isinstance(bespoke_optimization_schema.task_hashes, list)
    assert len(bespoke_optimization_schema.task_hashes) == 1
    assert isinstance(bespoke_optimization_schema.task_hashes[0], str)


def test_bespoke_ready_for_fitting(bespoke_optimization_schema):
    assert not bespoke_optimization_schema.ready_for_fitting


def test_bespoke_fitting_force_field(bespoke_optimization_schema):

    force_field = bespoke_optimization_schema.get_fitting_force_field()
    assert "parameterize" in force_field.to_string()


def test_bespoke_update_results_fitting_schema(bespoke_optimization_schema):
    """
    Make sure the fitting schema can correctly apply any results to the correct tasks.
    """

    results = TorsionDriveCollectionResult.parse_file(
        get_data_file_path(
            os.path.join("test", "qc-datasets", "biphenyl", "biphenyl.json.xz")
        )
    )
    bespoke_optimization_schema.update_with_results(results=results)
    # now make sure there are no tasks left
    assert bespoke_optimization_schema.ready_for_fitting


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


def test_bespoke_get_task_map(bespoke_optimization_schema):

    task_map = bespoke_optimization_schema.get_task_map()
    assert len(task_map) == 1


def test_bespoke_build_qcsubmit_datasets(bespoke_optimization_schema):

    data_sets = bespoke_optimization_schema.build_qcsubmit_datasets()
    assert len(data_sets) == 1

    data_set = data_sets[0]
    assert isinstance(data_set, TorsiondriveDataset)

    assert data_set.n_molecules == 1
    assert data_set.n_records == 1
