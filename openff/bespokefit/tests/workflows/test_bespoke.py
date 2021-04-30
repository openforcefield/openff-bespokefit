"""
Test for the bespoke-fit workflow generator.
"""
import os

import pytest
from openff.toolkit.topology import Molecule

from openff.bespokefit.exceptions import (
    ForceFieldError,
    FragmenterError,
    OptimizerError,
    TargetNotSetError,
)
from openff.bespokefit.schema.data import BespokeQCData
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.targets import (
    AbInitioTargetSchema,
    OptGeoTargetSchema,
    TorsionProfileTargetSchema,
    VibrationTargetSchema,
)
from openff.bespokefit.tests import does_not_raise
from openff.bespokefit.utilities import (
    get_data_file_path,
    get_molecule_cmiles,
    temporary_cd,
)
from openff.bespokefit.workflows.bespoke import BespokeWorkflowFactory

bace_entries = [
    "[h]c1c([c:1]([c:2](c(c1[h])[h])[c:3]2[c:4](c(c(c(c2[h])cl)[h])[h])[h])[h])[h]",
    "[h]c1c([c:1]([c:2](c(c1[h])[h])[c@:3]2(c(=o)n(c(=[n+:4]2[h])n([h])[h])c([h])([h])[h])c3(c(c3([h])[h])([h])[h])[h])[h])[h]",
    "[h]c1c(c(c(c(c1[h])[h])[c@:3]2(c(=o)n(c(=[n+:4]2[h])n([h])[h])c([h])([h])[h])[c:2]3([c:1](c3([h])[h])([h])[h])[h])[h])[h]",
]


@pytest.fixture()
def bace() -> Molecule:

    molecule: Molecule = Molecule.from_file(
        file_path=get_data_file_path(
            os.path.join("test", "molecules", "bace", "bace.sdf")
        ),
        file_format="sdf",
    )

    return molecule


@pytest.mark.parametrize(
    "force_field",
    [
        pytest.param(("openff-1.0.0.offxml", does_not_raise()), id="Parsley 1.0.0"),
        pytest.param(
            ("bespoke.offxml", pytest.raises(ForceFieldError)), id="Local forcefield"
        ),
        pytest.param(
            ("smirnoff99Frosst-1.0.7.offxml", does_not_raise()),
            id="Smirnoff99Frosst installed",
        ),
    ],
)
def test_check_force_field(force_field):
    """
    Make sure we only accept forcefields that have been installed.
    """
    force_file, expected_raises = force_field

    # Test the init validation
    with expected_raises:
        BespokeWorkflowFactory(initial_force_field=force_file)


@pytest.mark.parametrize(
    "optimization_data",
    [
        pytest.param(("ForceBalance", does_not_raise()), id="Forcebalance string pass"),
        pytest.param(
            ("BadOptimizer", pytest.raises(OptimizerError)), id="Missing optimizer"
        ),
        pytest.param(
            (ForceBalanceSchema(), does_not_raise()),
            id="Forcebalance class with target.",
        ),
    ],
)
def test_check_optimizer(optimization_data):
    """
    Test adding optimization stages to the workflow.
    """
    optimizer, expected_raises = optimization_data

    with expected_raises:
        factory = BespokeWorkflowFactory(optimizer=optimizer)
        assert factory.optimizer is not None


def test_workflow_export_import():
    """
    Test exporting and importing a workflow.
    """

    factory = BespokeWorkflowFactory(
        optimizer=ForceBalanceSchema(),
        target_templates=[AbInitioTargetSchema()],
    )

    with temporary_cd():

        factory.export_workflow(file_name="test.json")

        # now read it back in
        recreated = BespokeWorkflowFactory.parse_file("test.json")
        assert factory.dict() == recreated.dict()


@pytest.mark.parametrize(
    "input_kwargs, expected_raises",
    [
        (
            dict(target_templates=[]),
            pytest.raises(OptimizerError, match="There are no optimization targets"),
        ),
        (
            dict(fragmentation_engine=None),
            pytest.raises(FragmenterError, match="There is no fragmentation engine"),
        ),
        (
            dict(parameter_settings=[]),
            pytest.raises(TargetNotSetError, match="There are no parameter settings"),
        ),
        (
            dict(target_smirks=[]),
            pytest.raises(TargetNotSetError, match="No forcefield groups have"),
        ),
    ],
)
def test_pre_run_check(input_kwargs, expected_raises):
    """
    Make sure that the pre run check catches if there are no targets set up
    """
    factory = BespokeWorkflowFactory(**input_kwargs)

    with expected_raises:
        factory._pre_run_check()


@pytest.mark.parametrize(
    "target_schema",
    [
        TorsionProfileTargetSchema(reference_data=BespokeQCData()),
        AbInitioTargetSchema(reference_data=BespokeQCData()),
        VibrationTargetSchema(reference_data=BespokeQCData()),
        OptGeoTargetSchema(reference_data=BespokeQCData()),
    ],
)
def test_generate_fitting_task(target_schema, bace):
    """
    Make sure the correct fitting task is made based on the collection workflow.
    """
    molecule = Molecule.from_file(
        file_path=get_data_file_path(os.path.join("test", "molecules", "ethanol.sdf"))
    )

    task_schema = BespokeWorkflowFactory._generate_fitting_task(
        target_schema=target_schema,
        molecule=molecule,
        fragment=False,
        attributes=get_molecule_cmiles(molecule),
        dihedrals=[(8, 2, 1, 0)],
    )

    assert task_schema.task_type == target_schema.bespoke_task_type()


@pytest.mark.parametrize(
    "molecules",
    [
        get_data_file_path(os.path.join("test", "molecules", "ethanol.sdf")),
        Molecule.from_smiles("C"),
        [Molecule.from_smiles("C")] * 2,
    ],
)
def test_deduplicated_list(molecules):

    deduplicated = BespokeWorkflowFactory._deduplicated_list(molecules)
    assert deduplicated.n_molecules == 1


@pytest.mark.parametrize("processors", [1, 2])
def test_optimization_schemas_from_molecule(processors, bace):
    """
    Test the workflow function which makes the optimization schema from a molecule
    """

    factory = BespokeWorkflowFactory()

    opt_schemas = factory.optimization_schemas_from_molecules(
        molecules=bace, processors=processors
    )
    assert len(opt_schemas) == 1

    opt_schema = opt_schemas[0]

    assert opt_schema.initial_force_field == factory.initial_force_field
    assert opt_schema.optimizer == factory.optimizer
    assert opt_schema.id == "bespoke_task_0"
    assert bool(opt_schema.target_smirks) is True
    assert opt_schema.parameter_settings == factory.parameter_settings
    assert opt_schema.target_molecule.molecule == bace
    assert opt_schema.n_tasks == 3
    assert opt_schema.n_targets == 1


@pytest.mark.parametrize("combine, n_expected", [(True, 1), (False, 2)])
def test_sort_results(combine, n_expected, qc_torsion_drive_results):
    """
    Test sorting the results before making a fitting schema with and without combination.
    """

    records = qc_torsion_drive_results.to_records()
    records.append(records[0])

    sorted_results = BespokeWorkflowFactory._sort_results(records, combine=combine)

    assert len(sorted_results) == n_expected


def test_optimization_schema_from_records(qc_torsion_drive_results):
    """
    Test making an individual task from a set of QC records
    """

    factory = BespokeWorkflowFactory(optimizer=ForceBalanceSchema())

    records = qc_torsion_drive_results.to_records()

    # this should be a simple biphenyl molecule
    opt_schema = factory._optimization_schema_from_records(records=records, index=1)

    [(_, molecule)] = records

    assert opt_schema.initial_force_field == factory.initial_force_field
    assert opt_schema.optimizer == factory.optimizer
    assert opt_schema.id == "bespoke_task_1"
    assert bool(opt_schema.target_smirks) is True
    assert opt_schema.parameter_settings == factory.parameter_settings
    assert molecule == opt_schema.target_molecule.molecule
    assert opt_schema.n_tasks == 1
    assert opt_schema.n_targets == 1
    assert opt_schema.ready_for_fitting is True


def test_optimization_schemas_from_results(qc_torsion_drive_results):
    """
    Test that new fitting schemas can be made from results and that all results are full
    """

    factory = BespokeWorkflowFactory(optimizer=ForceBalanceSchema())

    schemas = factory.optimization_schemas_from_results(
        results=qc_torsion_drive_results, combine=True
    )

    assert len(schemas) == 1
    assert schemas[0].n_tasks == 1

    assert all(schema.ready_for_fitting for schema in schemas)