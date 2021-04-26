import copy
import os

from openff.bespokefit.schema.fitting import Status
from openff.bespokefit.schema.results import BespokeOptimizationResults
from openff.bespokefit.utilities import get_data_file_path
from openff.bespokefit.utilities.smirnoff import ForceFieldEditor


def test_bespoke_get_final_force_field(bespoke_optimization_schema):

    # TODO: This should be more comprehensively tested.

    force_field_editor = ForceFieldEditor(
        get_data_file_path(os.path.join("test", "force-fields", "bespoke.offxml"))
    )

    final_smirks = copy.deepcopy(bespoke_optimization_schema.target_smirks)
    force_field_editor.update_smirks_parameters(smirks=final_smirks)

    results = BespokeOptimizationResults(
        input_schema=bespoke_optimization_schema,
        provenance={},
        status=Status.Complete,
        final_smirks=final_smirks,
    )

    final_force_field = results.get_final_force_field(generate_bespoke_terms=False)
    assert final_force_field is not None
