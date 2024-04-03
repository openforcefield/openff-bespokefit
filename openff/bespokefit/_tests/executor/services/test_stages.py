import pytest
from openff.toolkit.typing.engines.smirnoff import ForceField

from openff.bespokefit.executor.services.coordinator.stages import QCGenerationStage


def test_generate_torsions(ptp1b_fragment, ptp1b_input_schema_single):
    """
    Make sure the optimisation stage can correctly regenerate torsion SMIRKS which hit both the parent and fragment molecule.
    """
    input_schema = ptp1b_input_schema_single.copy(deep=True)
    new_parameters, _ = QCGenerationStage._generate_torsion_parameters(
        fragmentation_result=ptp1b_fragment,
        input_schema=input_schema,
    )[0]
    # now check the new smirks hits the fragment and parent, for the same atoms
    parent_matches = set(
        ptp1b_fragment.parent_molecule.chemical_environment_matches(
            new_parameters.smirks,
        ),
    )
    fragment_matches = set(
        ptp1b_fragment.fragments[0].molecule.chemical_environment_matches(
            new_parameters.smirks,
        ),
    )
    # check number of unique matches is the same
    assert len(parent_matches) == len(fragment_matches)


@pytest.mark.asyncio
async def test_generate_parameters(ptp1b_input_schema_single, ptp1b_fragment):
    """
    Make sure that old parameters are generated for the stage
    """
    input_schema = ptp1b_input_schema_single.copy(deep=True)
    await QCGenerationStage._generate_parameters(
        fragmentation_result=ptp1b_fragment,
        input_schema=input_schema,
    )
    # make sure we have new parameters
    new_smirks = {parameter.smirks for parameter in input_schema.stages[0].parameters}
    # regression test the generated patterns
    assert new_smirks == {
        "[#6H1X3x2r6+0a:1](-;!@[#1H0X1x0!r+0A])(:;@[#6H0X3x2r6+0a,#6H1X3x2r6+0a](-;!@[#1H0X1x0!r+0A,#7H1X3x0!r+0A]):;@"
        "[#6H1X3x2r6+0a](-;!@[#1H0X1x0!r+0A]):;@[#6H0X3x2r6+0a,#6H1X3x2r6+0a](-;!@[#1H0X1x0!r+0A,#7H1X3x0!r+0A]):;@"
        "[#6H1X3x2r6+0a]-;!@[#1H0X1x0!r+0A]):;@[#6H0X3x2r6+0a:2]-;!@[#6H0X3x2r5+0A:3](=;@[#6H0X3x2r5+0A](-;!@"
        "[#35H0X1x0!r+0A])-;@[#6H0X3x2r5+0A](=;@[#6H0X3x2r5+0A,#6H1X3x2r5+0A]-;!@[#1H0X1x0!r+0A,#6H0X3x0!r+0A])-;!@"
        "[#8H0X2x0!r+0A]-;!@[#6H2X4x0!r+0A,#6H3X4x0!r+0A](-;!@[#1H0X1x0!r+0A,#6H0X3x0!r+0A])(-;!@[#1H0X1x0!r+0A])-;!@"
        "[#1H0X1x0!r+0A])-;@[#16H0X2x2r5+0A:4]",
        "[#6H1X3x2r6+0a:1](-;!@[#1H0X1x0!r+0A])(:;@[#6H0X3x2r6+0a,#6H1X3x2r6+0a](-;!@[#1H0X1x0!r+0A,#7H1X3x0!r+0A]):;@"
        "[#6H1X3x2r6+0a](-;!@[#1H0X1x0!r+0A]):;@[#6H0X3x2r6+0a,#6H1X3x2r6+0a](-;!@[#1H0X1x0!r+0A,#7H1X3x0!r+0A]):;@"
        "[#6H1X3x2r6+0a]-;!@[#1H0X1x0!r+0A]):;@[#6H0X3x2r6+0a:2]-;!@[#6H0X3x2r5+0A:3](-;@[#16H0X2x2r5+0A]-;@"
        "[#6H0X3x2r5+0A,#6H1X3x2r5+0A](-;!@[#1H0X1x0!r+0A,#6H0X3x0!r+0A])=;@[#6H0X3x2r5+0A]-;!@[#8H0X2x0!r+0A]-;!@"
        "[#6H2X4x0!r+0A,#6H3X4x0!r+0A](-;!@[#1H0X1x0!r+0A,#6H0X3x0!r+0A])(-;!@[#1H0X1x0!r+0A])-;!@[#1H0X1x0!r+0A])=;@"
        "[#6H0X3x2r5+0A:4]-;!@[#35H0X1x0!r+0A]",
    }
    assert len(new_smirks) == 2
    # make sure the smirks have been added to the force field
    force_field = ForceField(
        input_schema.initial_force_field,
        allow_cosmetic_attributes=True,
    )
    torsion_handler = force_field.get_parameter_handler("ProperTorsions")
    for smirks in new_smirks:
        assert smirks in torsion_handler.parameters


@pytest.mark.asyncio
async def test_generate_parameters_multiple_stages(
    ptp1b_input_schema_multiple,
    ptp1b_fragment,
):
    """Make sure parameters are correctly generated and assigned to the correct optimisation stage."""
    input_schema = ptp1b_input_schema_multiple.copy(deep=True)
    await QCGenerationStage._generate_parameters(
        fragmentation_result=ptp1b_fragment,
        input_schema=input_schema,
    )
    force_field = ForceField(
        input_schema.initial_force_field,
        allow_cosmetic_attributes=True,
    )
    # make sure we have the correct type of smirks for the hyper parameters
    for stage in input_schema.stages:
        smirks_types = {parameter.type for parameter in stage.parameter_hyperparameters}
        for parameter in stage.parameters:
            assert parameter.type in smirks_types
            # make sure the smirks is in the force field, this will not work for vdW/Atoms as the tags are not consistent
            assert (
                parameter.smirks
                in force_field.get_parameter_handler(parameter.type).parameters
            )
