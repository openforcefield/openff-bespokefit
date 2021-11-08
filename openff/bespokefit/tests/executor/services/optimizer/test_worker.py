import json

from openff.fragmenter.fragment import WBOFragmenter

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


def test_optimize(monkeypatch):

    input_schema = BespokeOptimizationSchema(
        smiles="CC",
        initial_force_field="openff-2.0.0.offxml",
        target_torsion_smirks=[],
        stages=[
            OptimizationStageSchema(
                parameters=[],
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
        stages=[OptimizationStageResults(provenance={}, status="running")],
    )

    received_schema = None

    def mock_optimize(schema, initial_force_field, keep_files=False):
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
