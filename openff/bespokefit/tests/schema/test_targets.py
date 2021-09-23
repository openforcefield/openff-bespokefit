import pytest
from pydantic import ValidationError
from qcelemental.models.common_models import Model

from openff.bespokefit.schema.data import BespokeQCData
from openff.bespokefit.schema.targets import TorsionProfileTargetSchema
from openff.bespokefit.schema.tasks import HessianTaskSpec, Torsion1DTaskSpec


def test_check_reference_data(qc_torsion_drive_results):

    # Handle the case of no bespoke data
    TorsionProfileTargetSchema(reference_data=qc_torsion_drive_results)

    # Handle the bespoke data case with a valid task.
    TorsionProfileTargetSchema(
        reference_data=BespokeQCData(
            spec=Torsion1DTaskSpec(
                model=Model(method="uff", basis=None), program="rdkit"
            )
        )
    )

    # Handle the case of an invalid task
    with pytest.raises(ValidationError):

        TorsionProfileTargetSchema(
            reference_data=BespokeQCData(
                spec=HessianTaskSpec(
                    model=Model(method="uff", basis=None), program="rdkit"
                )
            )
        )
