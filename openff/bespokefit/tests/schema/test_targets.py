import pytest
from pydantic import ValidationError

from openff.bespokefit.schema.data import BespokeQCData
from openff.bespokefit.schema.targets import (
    TorsionProfileTargetSchema,
    VibrationTargetSchema,
)


def test_check_reference_data(ethane_torsion_task, qc_torsion_drive_results):

    # Handle the case of no bespoke data
    TorsionProfileTargetSchema(reference_data=qc_torsion_drive_results)

    # Handle the bespoke data case with a valid task.
    TorsionProfileTargetSchema(
        reference_data=BespokeQCData(tasks=[ethane_torsion_task])
    )

    # Handle the case of an invalid task
    with pytest.raises(ValidationError):
        VibrationTargetSchema(reference_data=BespokeQCData(tasks=[ethane_torsion_task]))
