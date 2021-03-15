import os
from typing import Any, Dict

import pytest
from qcelemental.models import Molecule as QCMolecule
from qcelemental.util import deserialize
from qcportal import FractalClient
from qcportal.models import ResultRecord, TorsionDriveRecord

from openff.bespokefit.schema.fitting import OptimizationSchema
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.smirks import ProperTorsionSmirks
from openff.bespokefit.schema.smirnoff import ProperTorsionSettings
from openff.bespokefit.schema.targets import (
    AbInitioTargetSchema,
    ExistingQCData,
    OptGeoTargetSchema,
    TorsionProfileTargetSchema,
    VibrationTargetSchema,
)
from openff.bespokefit.utilities import get_data_file_path


def _parse_raw_qc_record(name: str) -> Dict[str, Any]:

    record_path = get_data_file_path(
        os.path.join("test", "qc-datasets", "raw", f"{name}.json")
    )
    record_cache_path = get_data_file_path(
        os.path.join("test", "qc-datasets", "raw", f"{name}-cache.json")
    )

    with open(record_path) as file:
        raw_qc_record = deserialize(file.read(), "json")

    with open(record_cache_path) as file:
        raw_qc_cache = deserialize(file.read(), "json")

        if "final_molecules" in raw_qc_cache:

            for grid_id, qc_molecule in raw_qc_cache["final_molecules"].items():

                qc_molecule = QCMolecule(**qc_molecule)
                raw_qc_cache["final_molecules"][grid_id] = qc_molecule

        elif "molecule" in raw_qc_cache:
            raw_qc_cache["molecule"] = QCMolecule(**raw_qc_cache["molecule"])

    raw_qc_record["cache"] = raw_qc_cache

    return raw_qc_record


@pytest.fixture()
def qc_torsion_drive_record() -> TorsionDriveRecord:
    return TorsionDriveRecord.parse_obj(_parse_raw_qc_record("td-1762148"))


@pytest.fixture()
def qc_optimization_record(monkeypatch) -> ResultRecord:

    monkeypatch.setattr(ResultRecord, "check_client", lambda *_: True)
    record = ResultRecord.parse_obj(_parse_raw_qc_record("opt-19530775"))

    return record


@pytest.fixture()
def qc_hessian_record(monkeypatch) -> ResultRecord:

    # We need to h
    monkeypatch.setattr(ResultRecord, "check_client", lambda *_: True)
    record = ResultRecord.parse_obj(_parse_raw_qc_record("hess-18854534"))

    return record


@pytest.fixture()
def general_optimization_schema(
    qc_torsion_drive_record: TorsionDriveRecord,
    qc_optimization_record: ResultRecord,
    qc_hessian_record: ResultRecord,
    monkeypatch
):

    records_by_id = {
        qc_torsion_drive_record.id: qc_torsion_drive_record,
        qc_optimization_record.id: qc_optimization_record,
        qc_hessian_record.id: qc_hessian_record,
    }

    # Mock the QC fractal client to retrieve our pre-calculated result records.
    def mock_query(*_, **kwargs):
        return [records_by_id[kwargs["id"]]]

    monkeypatch.setattr(FractalClient, "query_results", mock_query)
    monkeypatch.setattr(FractalClient, "query_procedures", mock_query)

    optimization_schema = OptimizationSchema(
        initial_force_field="openff-1.3.0.offxml",
        optimizer=ForceBalanceSchema(),
        targets=[
            TorsionProfileTargetSchema(
                reference_data=ExistingQCData(
                    record_ids=[qc_torsion_drive_record.id]
                )
            ),
            AbInitioTargetSchema(
                reference_data=ExistingQCData(
                    record_ids=[qc_torsion_drive_record.id]
                )
            ),
            VibrationTargetSchema(
                reference_data=ExistingQCData(
                    record_ids=[qc_hessian_record.id]
                )
            ),
            OptGeoTargetSchema(
                reference_data=ExistingQCData(
                    record_ids=[qc_optimization_record.id]
                )
            ),
        ],
        parameter_settings=[ProperTorsionSettings()],
        target_parameters=[
            ProperTorsionSmirks(
                smirks="[*:1]-[#6X4:2]-[#6X4:3]-[*:4]",
                attributes={"k1"}
            )
        ],
    )

    return optimization_schema
