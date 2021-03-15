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
    "instance, template_generator",
    [
        (AbInitioTargetSchema(), AbInitioTargetTemplate),
        (OptGeoTargetSchema(), OptGeoTargetTemplate),
        (TorsionProfileTargetSchema(), TorsionProfileTargetTemplate),
        (VibrationTargetSchema(), VibrationTargetTemplate),
    ]
)
def test_target_template_generate(instance, template_generator):

    contents = template_generator.generate(instance, ["tmp-name"])
    assert len(contents) > 0


def test_opt_get_options_generate():

    contents = OptGeoOptionsTemplate.generate(
        target=OptGeoTargetSchema(), record_ids=["a", "b"]
    )

    assert len(contents) > 0
    assert contents.find("system") != contents.rfind("system")


def test_input_options_generation():

    contents = InputOptionsTemplate.generate(
        settings=ForceBalanceSchema(),
        targets_section="",
        priors={"a": 0.1}
    )
    assert len(contents) > 0
