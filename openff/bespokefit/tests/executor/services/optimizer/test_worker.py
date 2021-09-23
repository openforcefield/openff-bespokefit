import json

from openff.bespokefit.optimizers import ForceBalanceOptimizer
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults
from openff.fragmenter.fragment import WBOFragmenter

from openff.bespokefit.executor.services.optimizer import worker


def test_optimize(monkeypatch):

    input_schema = BespokeOptimizationSchema(
        smiles="CC",
        initial_force_field="openff-2.0.0.offxml",
        parameters=[],
        parameter_hyperparameters=[],
        fragmentation_engine=WBOFragmenter(),
        targets=[],
        optimizer=ForceBalanceSchema(max_iterations=1),
    )
    input_schema_json = input_schema.json()

    expected_output = BespokeOptimizationResults(
        input_schema=input_schema, provenance={}, status="running"
    )

    received_schema = None

    def mock_optimize(schema, keep_files=False):
        nonlocal received_schema
        received_schema = schema

        return expected_output

    monkeypatch.setattr(ForceBalanceOptimizer, "optimize", mock_optimize)

    result_json = worker.optimize(optimization_input_json=input_schema_json)
    assert isinstance(result_json, str)

    result_dict = json.loads(result_json)
    assert isinstance(result_dict, dict)

    result = BespokeOptimizationResults.parse_obj(result_dict)
    assert result.status == expected_output.status

    assert received_schema.json() == input_schema_json
