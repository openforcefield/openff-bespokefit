import pytest
from pydantic import ValidationError
from qcelemental.models.common_models import Model

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
    "TargetSchema,qc_result_fixture",
    [
        (TorsionProfileTargetSchema, "qc_torsion_drive_qce_result"),
        (AbInitioTargetSchema, "qc_torsion_drive_qce_result"),
        (OptGeoTargetSchema, "qc_optimization_qce_result"),
    ],
)
def test_check_connectivity_local_positive(
    TargetSchema,
    qc_result_fixture,
    request,
):
    torsiondrive_result, _ = request.getfixturevalue(qc_result_fixture)

    TargetSchema(reference_data=LocalQCData(qc_records=[torsiondrive_result]))


@pytest.mark.parametrize(
    "TargetSchema,qc_result_fixture",
    [
        (TorsionProfileTargetSchema, "qc_torsion_drive_qce_result"),
        (AbInitioTargetSchema, "qc_torsion_drive_qce_result"),
        (OptGeoTargetSchema, "qc_optimization_qce_result"),
    ],
)
def test_check_connectivity_local_negative(
    TargetSchema,
    qc_result_fixture,
    request,
):
    torsiondrive_result, _ = request.getfixturevalue(qc_result_fixture)

    # Swap the first two atoms' coordinates to break their connectivity
    torsiondrive_result_disconnection = torsiondrive_result.copy()
    try:
        geom = next(
            iter(torsiondrive_result_disconnection.final_molecules.values())
        ).geometry
    except AttributeError:
        geom = torsiondrive_result_disconnection.final_molecule.geometry
    geom[0], geom[1] = geom[1], geom[0]

    expected_err = (
        r"1 validation error for "
        + TargetSchema.__name__
        + r"\n"
        + r"reference_data\n"
        + r"  Target record (opt|\[-165\]): Reference data "
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
        + r" \(type=value_error\)"
    )
    with pytest.raises(ValidationError, match=expected_err):
        TargetSchema(
            reference_data=LocalQCData(qc_records=[torsiondrive_result_disconnection])
        )


@pytest.mark.parametrize(
    "TargetSchema,qc_result_fixture",
    [
        (TorsionProfileTargetSchema, "qc_torsion_drive_results"),
        (AbInitioTargetSchema, "qc_torsion_drive_results"),
        (OptGeoTargetSchema, "qc_optimization_results"),
    ],
)
def test_check_connectivity_qcfractal_positive(
    TargetSchema,
    qc_result_fixture,
    request,
):
    torsiondrive_result_collection = request.getfixturevalue(qc_result_fixture)

    TargetSchema(reference_data=torsiondrive_result_collection)


@pytest.mark.parametrize(
    "TargetSchema,qc_result_fixture",
    [
        (TorsionProfileTargetSchema, "qc_torsion_drive_results"),
        (AbInitioTargetSchema, "qc_torsion_drive_results"),
        (OptGeoTargetSchema, "qc_optimization_results"),
    ],
)
def test_check_connectivity_qcfractal_negative(
    TargetSchema,
    qc_result_fixture,
    request,
):
    collection = request.getfixturevalue(qc_result_fixture)

    [(record, _)] = collection.to_records()

    # Get the first of the final molecules, and prepare an update function so
    # that changes are preserved across calls to get_final_molecule(s)()
    try:
        final_molecules = record.get_final_molecules()
        key, first_final_mol = next(iter(record.cache["final_molecules"].items()))

        def update_record(updated_mol):
            final_molecules.update({key: updated_mol})
            record.__dict__["get_final_molecules"] = lambda: final_molecules

    except AttributeError:
        first_final_mol = record.get_final_molecule()

        def update_record(updated_mol):
            record.__dict__["get_final_molecule"] = lambda: updated_mol

    # Swap the first two atoms' coordinates to break their connectivity
    geom = first_final_mol.geometry.copy()
    geom[0], geom[1] = geom[1], geom[0]
    updated_mol = first_final_mol.copy(update={"geometry": geom})

    # Update the record with the new geometry
    update_record(updated_mol)

    # Create the target schema, which should fail to validate
    expected_err = (
        r"1 validation error for "
        + TargetSchema.__name__
        + r"\n"
        + r"reference_data\n"
        + r"  Target record (opt|\[-165\]): Reference data "
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
        + r" \(type=value_error\)"
    )
    with pytest.raises(ValidationError, match=expected_err):
        TargetSchema(reference_data=collection)
