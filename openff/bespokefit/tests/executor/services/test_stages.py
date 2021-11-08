import pytest
from openff.toolkit.typing.engines.smirnoff import ForceField, ParameterLookupError

from openff.bespokefit.executor.services.coordinator.stages import OptimizationStage


def test_regenerate_torsions(ptp1b_fragment):
    """
    Make sure the optimisation stage can correctly regenerate torsion SMIRKS which hit both the parent and fragment molecule.
    """
    new_parameter = OptimizationStage._regenerate_torsion_parameters(
        fragmentation_result=ptp1b_fragment,
        initial_force_field="openff_unconstrained-1.3.0.offxml",
    )[0]
    # now check the new smirks hits the fragment and parent, for the same atoms
    parent_matches = set(
        ptp1b_fragment.parent_molecule.chemical_environment_matches(
            new_parameter.smirks
        )
    )
    fragment_matches = set(
        ptp1b_fragment.fragments[0].molecule.chemical_environment_matches(
            new_parameter.smirks
        )
    )
    # check number of unique matches is the same
    assert len(parent_matches) == len(fragment_matches)


@pytest.mark.asyncio
async def test_regenerate_parameters(ptp1b_input_schema, ptp1b_fragment):
    """
    Make sure that old parameters are removed from the input schema when new ones are generated.
    """
    input_schema = ptp1b_input_schema.copy(deep=True)
    # make a copy of the original parameters
    parameters = input_schema.stages[0].parameters
    old_smirks = {parameter.smirks for parameter in parameters}
    await OptimizationStage._regenerate_parameters(
        fragmentation_result=ptp1b_fragment, input_schema=input_schema
    )
    # now make sure the parameters are different
    new_smirks = {parameter.smirks for parameter in input_schema.stages[0].parameters}
    assert new_smirks.difference(old_smirks) != set()
    # the old patterns should be removed for the force field
    force_field = ForceField(
        input_schema.initial_force_field, allow_cosmetic_attributes=True
    )
    torsion_handler = force_field.get_parameter_handler("ProperTorsions")
    for smirks in old_smirks:
        with pytest.raises(ParameterLookupError):
            _ = torsion_handler.parameters[smirks]

    # the new parameters should be in the force field
    for smirks in new_smirks:
        _ = torsion_handler.parameters[smirks]
