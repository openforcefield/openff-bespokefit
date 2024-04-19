import json

from openff.fragmenter.fragment import WBOFragmenter
from openff.toolkit.typing.engines.smirnoff import ForceField

from openff.bespokefit.executor.services.coordinator.utils import _hash_fitting_schema
from openff.bespokefit.executor.services.optimizer import worker
from openff.bespokefit.optimizers import ForceBalanceOptimizer
from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationStageSchema,
)
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.results import (
    BespokeOptimizationResults,
    OptimizationStageResults,
)
from openff.bespokefit.schema.smirnoff import ProperTorsionSMIRKS


def test_optimize(monkeypatch, redis_connection):
    """
    Mock an optimisation and make sure the parameter cache is updated with fitted parameters
    """
    input_schema = BespokeOptimizationSchema(
        id="test",
        smiles="CC",
        initial_force_field="openff-2.2.0.offxml",
        initial_force_field_hash="test_hash",
        target_torsion_smirks=[],
        stages=[
            OptimizationStageSchema(
                parameters=[
                    ProperTorsionSMIRKS(
                        smirks="[*:1]-[#6X4:2]-[#6X4:3]-[*:4]", attributes={"k1"}
                    )
                ],
                parameter_hyperparameters=[],
                targets=[],
                optimizer=ForceBalanceSchema(max_iterations=1),
            )
        ],
        fragmentation_engine=WBOFragmenter(),
    )
    input_schema_json = input_schema.json()

    expected_output = BespokeOptimizationResults(
        input_schema=input_schema,
        stages=[
            OptimizationStageResults(
                provenance={},
                status="success",
                refit_force_field=ForceField("openff-2.2.0.offxml").to_string(),
            )
        ],
    )

    received_schema = None

    def mock_optimize(
        schema, initial_force_field, keep_files=False, root_directory=None
    ):
        nonlocal received_schema
        received_schema = schema

        return expected_output.stages[0]

    monkeypatch.setattr(ForceBalanceOptimizer, "optimize", mock_optimize)

    result_json = worker.optimize(optimization_input_json=input_schema_json)
    assert isinstance(result_json, str)

    result_dict = json.loads(result_json)
    assert isinstance(result_dict, dict)

    result = BespokeOptimizationResults.parse_obj(result_dict)
    assert result.status == expected_output.status

    assert received_schema.json() == input_schema.stages[0].json()

    # make sure the ff parameters were cached
    task_hash = _hash_fitting_schema(fitting_schema=result.input_schema)
    cached_ff_string = redis_connection.get(task_hash)
    assert cached_ff_string is not None

    # make sure our expected parameter has been cached
    cached_ff = ForceField(cached_ff_string)
    torsion_handler = cached_ff.get_parameter_handler("ProperTorsions")
    assert "[*:1]-[#6X4:2]-[#6X4:3]-[*:4]" in torsion_handler.parameters


def test_optimise_cache(bespoke_optimization_schema):
    """
    Make sure any stages with cached parameters are skipped and a mock result is returned.
    """

    result_json = worker.optimize(
        optimization_input_json=bespoke_optimization_schema.json()
    )
    result = BespokeOptimizationResults.parse_raw(result_json)
    assert result.status == "success"
    assert result.stages[0].provenance["skipped"] == "True"
