"""
Test all parts of the fitting schema.
"""
import pytest
from openff.qcsubmit.common_structures import QCSpec
from openff.qcsubmit.datasets import TorsiondriveDataset

from openff.bespokefit.exceptions import QCRecordMissMatchError
from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationSchema,
)


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


def test_bespoke_update_results_fitting_schema(
    bespoke_optimization_schema, qc_torsion_drive_results
):
    """
    Make sure the fitting schema can correctly apply any results to the correct tasks.
    """

    records = qc_torsion_drive_results.to_records()

    [(record, molecule)] = records

    bespoke_optimization_schema.targets[0].reference_data.qc_spec = QCSpec(
        method=record.qc_spec.method,
        basis=record.qc_spec.basis,
        program=record.qc_spec.program,
    )

    bespoke_optimization_schema.update_with_results(records)
    # now make sure there are no tasks left
    assert bespoke_optimization_schema.ready_for_fitting


def test_bespoke_update_results_wrong_spec(
    bespoke_optimization_schema, qc_torsion_drive_results
):
    """
    Make sure the fitting schema can correctly apply any results to the correct tasks.
    """

    records = qc_torsion_drive_results.to_records()

    [(record, molecule)] = records

    bespoke_optimization_schema.targets[0].reference_data.qc_spec = QCSpec(
        method="hf",
        basis="6-31G",
        program=record.qc_spec.program,
    )

    with pytest.raises(QCRecordMissMatchError):
        bespoke_optimization_schema.update_with_results(records)


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
