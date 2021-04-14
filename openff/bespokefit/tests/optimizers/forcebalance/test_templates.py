import pytest

from openff.bespokefit.optimizers.forcebalance.templates import (
    AbInitioTargetTemplate,
    InputOptionsTemplate,
    OptGeoOptionsTemplate,
    OptGeoTargetTemplate,
    TorsionProfileTargetTemplate,
    VibrationTargetTemplate,
)
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.targets import (
    AbInitioTargetSchema,
    OptGeoTargetSchema,
    TorsionProfileTargetSchema,
    VibrationTargetSchema,
)


@pytest.mark.parametrize(
    "instance, template_generator, expected_lines",
    [
        (
            AbInitioTargetSchema(extras={"remote": "1"}),
            AbInitioTargetTemplate,
            [
                "name tmp-name",
                "weight 1.0",
                "type AbInitio_SMIRNOFF",
                "attenuate 0",
                "energy_denom 1.0",
                "energy_upper 10.0",
                "energy 1",
                "force 0",
                "remote 1",
            ],
        ),
        (
            OptGeoTargetSchema(extras={"remote": "1"}),
            OptGeoTargetTemplate,
            [
                "name tmp-name",
                "weight 1.0",
                "type OptGeoTarget_SMIRNOFF",
                "remote 1",
            ],
        ),
        (
            TorsionProfileTargetSchema(extras={"remote": "1"}),
            TorsionProfileTargetTemplate,
            [
                "name tmp-name",
                "weight 1.0",
                "type TorsionProfile_SMIRNOFF",
                "attenuate 1",
                "energy_denom 1.0",
                "energy_upper 10.0",
                "remote 1",
            ],
        ),
        (
            VibrationTargetSchema(extras={"remote": "1"}),
            VibrationTargetTemplate,
            [
                "name tmp-name",
                "weight 1.0",
                "type VIBRATION_SMIRNOFF",
                "remote 1",
            ],
        ),
        (
            VibrationTargetSchema(mode_reassignment="overlap"),
            VibrationTargetTemplate,
            ["reassign overlap"],
        ),
    ],
)
def test_target_template_generate(instance, template_generator, expected_lines):

    contents = template_generator.generate(instance, ["tmp-name"])

    assert len(contents) > 0

    for line in expected_lines:
        assert line in contents


def test_opt_get_options_generate():

    contents = OptGeoOptionsTemplate.generate(
        target=OptGeoTargetSchema(), record_ids=["a", "b"]
    )

    assert len(contents) > 0

    assert contents.find("system") != contents.rfind("system")

    assert "bond_denom 0.05" in contents
    assert "angle_denom 8.0" in contents
    assert "dihedral_denom 0.0" in contents
    assert "improper_denom 20.0" in contents


def test_input_options_generation():

    contents = InputOptionsTemplate.generate(
        settings=ForceBalanceSchema(), targets_section="", priors={"a": 0.1}
    )
    assert len(contents) > 0

    # Check the priors are in the input.
    assert "a :  0.1" in contents


# def test_generate_opt_in():
#     """
#     Test generating the optimize in file with various input settings.
#     """
#     fb = ForceBalanceOptimizer(penalty_type="L1", max_iterations=150)
#
#     # make sure an error is raised if the targets were not set
#     with temp_directory():
#         with pytest.raises(TargetNotSetError):
#             fb.generate_optimize_in(priors={"test": 1.23}, fitting_targets={"AbInitio_SMIRNOFF": ["job1", "job2"]})
#
#         # now set them and run again
#         fb.set_optimization_target(AbInitio_SMIRNOFF())
#         fb.generate_optimize_in(priors={"test": 1.23}, fitting_targets={"AbInitio_SMIRNOFF": ["job1", "job2"]})
#
#         # now load in the file and check the attributes
#         with open("optimize.in") as opt_in:
#             data = opt_in.readlines()
#             assert "   test :  1.23\n" in data
#             assert "penalty_type L1\n" in data
#             assert "maxstep 150\n" in data
#             assert "type AbInitio_SMIRNOFF\n" in data
#             assert "name job1\n" in data
#             assert "name job2\n" in data
