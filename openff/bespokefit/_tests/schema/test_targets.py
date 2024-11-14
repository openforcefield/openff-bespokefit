import pytest
import qcportal
from qcelemental.models.common_models import Model

from openff.bespokefit._pydantic import ValidationError
from openff.bespokefit.schema.data import BespokeQCData, LocalQCData
from openff.bespokefit.schema.targets import (
    AbInitioTargetSchema,
    OptGeoTargetSchema,
    TorsionProfileTargetSchema,
)
from openff.bespokefit.schema.tasks import HessianTaskSpec, Torsion1DTaskSpec


def test_check_reference_data(qc_torsion_drive_results):
    # Handle the case of no bespoke data
    TorsionProfileTargetSchema(reference_data=qc_torsion_drive_results)

    # Handle the bespoke data case with a valid task.
    TorsionProfileTargetSchema(
        reference_data=BespokeQCData(
            spec=Torsion1DTaskSpec(
                program="rdkit", model=Model(method="uff", basis=None)
            )
        )
    )

    # Handle the case of an invalid task
    with pytest.raises(ValidationError):
        TorsionProfileTargetSchema(
            reference_data=BespokeQCData(
                spec=HessianTaskSpec(
                    program="rdkit", model=Model(method="uff", basis=None)
                )
            )
        )


@pytest.mark.parametrize(
    "TargetSchema",
    [
        TorsionProfileTargetSchema,
        AbInitioTargetSchema,
        OptGeoTargetSchema,
    ],
)
class TestCheckConnectivity:
    @pytest.fixture()
    def expected_err(self, TargetSchema) -> str:
        return (
            r"1 validation error for "
            + TargetSchema.__name__
            + r"\n"
            + r"reference_data\n"
            + r"  Target record .*: Reference data "
            + r"does not match target\.\n"
            + r"Expected mapped SMILES: "
            # This regex for the mapped SMILES is probably extremely fragile;
            # if this test breaks after an RDkit/OpenEye update, try replacing it
            # with something like `+ r".*"`
            + r"(\(?[-+]?\[("
            + r"H:13|c:1|c:3|c:7|c:11|c:8|c:4|H:16|H:20|c:12|c:9|c:5|c:2|c:6|c:10"
            + r"|H:22|H:18|H:14|H:17|H:21|H:19|H:15"
            + r")\]1?2?\)?){22}"
            # End fragile regex
            + r"\n"
            + r"The following connections were expected but not found: "
            + r"{\(1, 13\), \(1, 3\), \(1, 4\)}\n"
            + r"The following connections were found but not expected: "
            + r"{\(1, 6\), \(1, 2\), \(1, 14\), \(1, 5\)}\n"
            + r"The reference geometry is: \[(\[.*\]\n ){21}\[.*\]\]"
            # + r"The reference geometry is: \[.*\]"
            + r" \(type=value_error\)"
        )

    @pytest.fixture()
    def ref_data_local(self, TargetSchema, request):
        ref_data_fixture = {
            TorsionProfileTargetSchema: "qc_torsion_drive_qce_result",
            AbInitioTargetSchema: "qc_torsion_drive_qce_result",
            OptGeoTargetSchema: "qc_optimization_qce_result",
        }[TargetSchema]
        result, _ = request.getfixturevalue(ref_data_fixture)
        return [result]

    @pytest.fixture()
    def ref_data_qcfractal(self, TargetSchema, request):
        ref_data_fixture = {
            TorsionProfileTargetSchema: "qc_torsion_drive_results",
            AbInitioTargetSchema: "qc_torsion_drive_results",
            OptGeoTargetSchema: "qc_optimization_results",
        }[TargetSchema]
        return request.getfixturevalue(ref_data_fixture)

    def test_check_connectivity_local_positive(
        self,
        TargetSchema,
        ref_data_local,
    ):
        TargetSchema(reference_data=LocalQCData(qc_records=ref_data_local))

    def test_check_connectivity_local_negative(
        self,
        TargetSchema,
        ref_data_local,
        expected_err,
    ):
        # Swap the first two atoms' coordinates to break their connectivity
        torsiondrive_result_disconnection = ref_data_local[0]
        try:
            geom = next(
                iter(torsiondrive_result_disconnection.final_molecules.values())
            ).geometry
        except AttributeError:
            geom = torsiondrive_result_disconnection.final_molecule.geometry
        geom[0], geom[1] = geom[1], geom[0]

        with pytest.raises(ValidationError, match=expected_err):
            TargetSchema(
                reference_data=LocalQCData(
                    qc_records=[torsiondrive_result_disconnection]
                )
            )

    def test_check_connectivity_qcfractal_positive(
        self,
        TargetSchema,
        ref_data_qcfractal,
    ):
        TargetSchema(reference_data=ref_data_qcfractal)

    def test_check_connectivity_qcfractal_negative(
        self,
        TargetSchema,
        ref_data_qcfractal,
        expected_err,
    ):
        # record is a qcportal.torsiondrive.TorsionDriveRecord
        [(record, _)] = ref_data_qcfractal.to_records()

        # Get the first of the final molecules, and prepare an update function so
        # that changes are preserved across calls to get_final_molecule(s)()

        def modify_molecule(molecule):
            pass

        if isinstance(record, qcportal.torsiondrive.TorsiondriveRecord):

            for _record in record.minimum_optimizations.values():
                pos0 = _record.final_molecule.geometry[0]
                pos1 = _record.final_molecule.geometry[1]
                _record.final_molecule.geometry[0] = pos1
                _record.final_molecule.geometry[1] = pos0

        else:
            pos0 = record.final_molecule.geometry[0]
            pos1 = record.final_molecule.geometry[1]
            record.final_molecule.geometry[0] = pos1
            record.final_molecule.geometry[1] = pos0

        # Create the target schema, which should fail to validate
        with pytest.raises(ValidationError, match=expected_err):
            TargetSchema(reference_data=ref_data_qcfractal)
