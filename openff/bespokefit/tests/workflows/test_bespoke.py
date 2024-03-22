"""
Test for the bespoke-fit workflow generator.
"""
import os

import pytest
from openff.fragmenter.fragment import WBOFragmenter
from openff.qcsubmit.common_structures import QCSpec
from openff.toolkit.typing.engines.smirnoff import ForceField, Molecule
from openff.utilities import get_data_file_path, temporary_cd

from openff.bespokefit._pydantic import ValidationError
from openff.bespokefit.exceptions import (
    MissingTorsionTargetSMARTS,
    OptimizerError,
    TargetNotSetError,
)
from openff.bespokefit.schema.data import BespokeQCData
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.smirnoff import (
    BondHyperparameters,
    ProperTorsionHyperparameters,
)
from openff.bespokefit.schema.targets import AbInitioTargetSchema
from openff.bespokefit.schema.tasks import Torsion1DTaskSpec
from openff.bespokefit.tests import does_not_raise
from openff.bespokefit.workflows.bespoke import (
    _DEFAULT_ROTATABLE_SMIRKS,
    BespokeWorkflowFactory,
)


@pytest.mark.parametrize(
    "force_field",
    [
        pytest.param(("openff-1.0.0.offxml", does_not_raise()), id="Parsley 1.0.0"),
        pytest.param(
            (ForceField("openff-1.0.0.offxml").to_string(), does_not_raise()),
            id="Local Force Field",
        ),
        pytest.param(
            ("BAD STRING", pytest.raises(IOError, match="Parsing failed")),
            id="Invalid FF",
        ),
    ],
)
def test_check_force_field(force_field):
    """Make sure we only accept force fields that have been installed."""

    force_field, expected_raises = force_field

    # Test the init validation
    with expected_raises:
        BespokeWorkflowFactory(initial_force_field=force_field)


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


def test_check_target_torsion_smirks():
    # Check the trivial case
    factory = BespokeWorkflowFactory(target_torsion_smirks=["[*:1]~[*:2]"])
    assert factory.target_torsion_smirks == ["[*:1]~[*:2]"]

    with pytest.raises(ValidationError, match="target_torsion_smirks"):
        BespokeWorkflowFactory(target_torsion_smirks=["[*:1]~[*:2]~[*:3]"])

    factory = BespokeWorkflowFactory(target_torsion_smirks=None)
    assert factory.target_torsion_smirks is None


@pytest.mark.parametrize(
    "input_kwargs, expected_raises",
    [
        pytest.param(
            dict(target_templates=[]),
            pytest.raises(OptimizerError, match="There are no optimization targets"),
            id="OptimizerError",
        ),
        pytest.param(
            dict(fragmentation_engine=WBOFragmenter(), target_torsion_smirks=None),
            pytest.raises(
                MissingTorsionTargetSMARTS, match="The `target_torsion_smirks`"
            ),
            id="Fragmenter, no torsion smirks",
        ),
        pytest.param(
            dict(
                fragmentation_engine=None,
                target_torsion_smirks=None,
                parameter_hyperparameters=[ProperTorsionHyperparameters()],
            ),
            pytest.raises(
                MissingTorsionTargetSMARTS, match="The `target_torsion_smirks`"
            ),
            id="No frgamenter, no target torsions",
        ),
        pytest.param(
            dict(parameter_hyperparameters=[]),
            pytest.raises(TargetNotSetError, match="There are no parameter settings"),
            id="TargetError",
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
    "filename",
    [pytest.param("test.yaml", id="yaml"), pytest.param("test.json", id="json")],
)
def test_export_factory(filename):
    """Test exporting and importing a workflow."""

    factory = BespokeWorkflowFactory(
        optimizer=ForceBalanceSchema(),
        target_templates=[AbInitioTargetSchema()],
    )

    with temporary_cd():
        factory.to_file(file_name=filename)

        # now read it back in
        recreated = BespokeWorkflowFactory.from_file(file_name=filename)
        assert factory.dict() == recreated.dict()


@pytest.mark.parametrize(
    "molecules",
    [
        get_data_file_path(
            os.path.join("test", "molecules", "ethanol.sdf"), "openff.bespokefit"
        ),
        Molecule.from_smiles("C"),
        [Molecule.from_smiles("C")] * 2,
    ],
)
def test_deduplicated_list(molecules):
    deduplicated = BespokeWorkflowFactory._deduplicated_list(molecules)
    assert deduplicated.n_molecules == 1


@pytest.mark.parametrize(
    "func_name",
    [
        "optimization_schemas_from_molecules",
        "optimization_schema_from_molecule",
    ],
)
def test_optimization_schemas_from_molecule(func_name):
    """
    Test the workflow function which makes the optimization schema from a molecule
    """

    factory = BespokeWorkflowFactory()
    factory_func = getattr(factory, func_name)

    molecule: Molecule = Molecule.from_smiles("c1ccc(cc1)c2ccccc2")

    opt_schema = factory_func(molecule)

    if func_name == "optimization_schemas_from_molecules":
        assert len(opt_schema) == 1
        opt_schema = opt_schema[0]

    assert len(opt_schema.stages[0].parameters) == 0

    assert opt_schema.stages[0].optimizer == factory.optimizer
    assert opt_schema.id == "bespoke_task_0"
    assert (
        opt_schema.stages[0].parameter_hyperparameters
        == factory.parameter_hyperparameters
    )
    assert Molecule.from_smiles(opt_schema.smiles) == molecule
    assert opt_schema.stages[0].n_targets == 1
    assert isinstance(opt_schema.stages[0].targets[0].reference_data, BespokeQCData)
    assert isinstance(
        opt_schema.stages[0].targets[0].reference_data.spec, Torsion1DTaskSpec
    )


@pytest.mark.parametrize(
    "workflow_settings, expected_output",
    [
        pytest.param(
            dict(
                fragmentation_engine=None,
                parameter_hyperparameters=[ProperTorsionHyperparameters()],
                target_torsion_smirks=[_DEFAULT_ROTATABLE_SMIRKS],
            ),
            dict(
                target_torsion_smirks=[_DEFAULT_ROTATABLE_SMIRKS],
                fragmentation_engine=None,
            ),
            id="No fragmentation, torsion fitting",
        ),
        pytest.param(
            dict(
                fragmentation_engine=None,
                parameter_hyperparameters=[BondHyperparameters()],
                target_torsion_smirks=[_DEFAULT_ROTATABLE_SMIRKS],
            ),
            dict(target_torsion_smirks=None, fragmentation_engine=None),
            id="No fragmentation, no torsion fitting",
        ),
        pytest.param(
            dict(
                fragmentation_engine=WBOFragmenter(),
                parameter_hyperparameters=[BondHyperparameters()],
                target_torsion_smirks=[_DEFAULT_ROTATABLE_SMIRKS],
            ),
            dict(
                fragmentation_engine=WBOFragmenter(),
                target_torsion_smirks=[_DEFAULT_ROTATABLE_SMIRKS],
            ),
            id="Fragmentation, no torsion fitting",
        ),
    ],
)
def test_optimization_schema_from_molecule_fragmentation(
    workflow_settings, expected_output, bace
):
    """
    Test creating the optimization schema from a molecule with different fragmentation settings.
    """
    factory = BespokeWorkflowFactory(**workflow_settings)

    schema = factory.optimization_schema_from_molecule(molecule=bace)
    for key, value in expected_output.items():
        assert getattr(schema, key) == value


@pytest.mark.parametrize("combine, n_expected", [(True, 1), (False, 2)])
def test_group_records(combine, n_expected, qc_torsion_drive_results):
    """
    Test sorting the results before making a fitting schema with and without combination.
    """

    records = qc_torsion_drive_results.to_records()
    records.append(records[0])

    sorted_results = BespokeWorkflowFactory._group_records(records, combine=combine)

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

    ForceField(opt_schema.initial_force_field)

    assert opt_schema.stages[0].optimizer == factory.optimizer
    assert opt_schema.id == "bespoke_task_1"
    assert bool(opt_schema.stages[0].parameters) is False
    assert (
        opt_schema.stages[0].parameter_hyperparameters
        == factory.parameter_hyperparameters
    )
    assert molecule == Molecule.from_mapped_smiles(opt_schema.smiles)
    assert opt_schema.stages[0].n_targets == 1


def test_optimization_schemas_from_results(qc_torsion_drive_results):
    """
    Test that new fitting schemas can be made from results and that all results are full
    """

    factory = BespokeWorkflowFactory(optimizer=ForceBalanceSchema())

    schemas = factory.optimization_schemas_from_results(
        results=qc_torsion_drive_results, combine=True, processors=1
    )

    assert len(schemas) == 1


def test_select_qc_spec():
    default_qc_spec = QCSpec(program="rdkit", method="uff", basis=None)

    factory = BespokeWorkflowFactory(default_qc_specs=[default_qc_spec])
    assert factory._select_qc_spec(Molecule.from_smiles("C")) == default_qc_spec
