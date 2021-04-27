import os
from typing import Any, Dict, Tuple

import pytest
from openff.qcsubmit.results import (
    BasicResult,
    BasicResultCollection,
    OptimizationResult,
    OptimizationResultCollection,
    TorsionDriveResult,
    TorsionDriveResultCollection,
)
from openff.toolkit.topology import Molecule
from qcelemental.util import deserialize
from qcportal import FractalClient
from qcportal.models import (
    ObjectId,
    OptimizationRecord,
    ResultRecord,
    TorsionDriveRecord,
)
from simtk import unit

from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationSchema,
)
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.smirks import ProperTorsionSmirks
from openff.bespokefit.schema.smirnoff import ProperTorsionSettings
from openff.bespokefit.schema.targets import (
    AbInitioTargetSchema,
    OptGeoTargetSchema,
    TorsionProfileTargetSchema,
    VibrationTargetSchema,
)
from openff.bespokefit.utilities import get_data_file_path
from openff.bespokefit.workflows.bespoke import BespokeWorkflowFactory


def _smiles_to_molecule(smiles: str) -> Molecule:

    molecule: Molecule = Molecule.from_smiles(smiles, allow_undefined_stereo=True)
    molecule.generate_conformers(n_conformers=1)

    return molecule


def _parse_raw_qc_record(name: str) -> Dict[str, Any]:

    record_path = get_data_file_path(
        os.path.join("test", "qc-datasets", "raw", f"{name}.json")
    )

    with open(record_path) as file:
        raw_qc_record = deserialize(file.read(), "json")

    return raw_qc_record


@pytest.fixture(scope="module")
def qc_torsion_drive_record() -> Tuple[TorsionDriveRecord, Molecule]:

    [(record, molecule)] = TorsionDriveResultCollection(
        entries={
            "api.qcarchive.molssi.org:443": [
                TorsionDriveResult(
                    record_id=ObjectId("21272387"),
                    cmiles="[H:13][c:1]1[c:3]([c:7]([c:11]([c:8]([c:4]1[H:16])[H:20])"
                    "[c:12]2[c:9]([c:5]([c:2]([c:6]([c:10]2[H:22])[H:18])[H:14])"
                    "[H:17])[H:21])[H:19])[H:15]",
                    inchi_key="ZUOUZKKEUPVFJK-UHFFFAOYSA-N",
                )
            ]
        }
    ).to_records()

    return record, molecule


@pytest.fixture()
def qc_torsion_drive_results(
    qc_torsion_drive_record, monkeypatch
) -> TorsionDriveResultCollection:

    _, molecule = qc_torsion_drive_record

    collection = TorsionDriveResultCollection(
        entries={
            "http://localhost:442": [
                TorsionDriveResult(
                    record_id=ObjectId("1"),
                    cmiles=molecule.to_smiles(mapped=True),
                    inchi_key=molecule.to_inchikey(),
                )
            ]
        }
    )

    monkeypatch.setattr(
        TorsionDriveResultCollection,
        "to_records",
        lambda self: [qc_torsion_drive_record],
    )

    return collection


@pytest.fixture(scope="module")
def qc_optimization_record() -> Tuple[OptimizationRecord, Molecule]:

    [(record, molecule)] = OptimizationResultCollection(
        entries={
            "api.qcarchive.molssi.org:443": [
                OptimizationResult(
                    record_id=ObjectId("18433218"),
                    cmiles="[H:13][c:1]1[c:3]([c:7]([c:11]([c:8]([c:4]1[H:16])[H:20])"
                    "[c:12]2[c:9]([c:5]([c:2]([c:6]([c:10]2[H:22])[H:18])[H:14])"
                    "[H:17])[H:21])[H:19])[H:15]",
                    inchi_key="ZUOUZKKEUPVFJK-UHFFFAOYSA-N",
                )
            ]
        }
    ).to_records()

    return record, molecule


@pytest.fixture()
def qc_optimization_results(
    qc_optimization_record, monkeypatch
) -> OptimizationResultCollection:

    _, molecule = qc_optimization_record

    collection = OptimizationResultCollection(
        entries={
            "http://localhost:442": [
                OptimizationResult(
                    record_id=ObjectId("1"),
                    cmiles=molecule.to_smiles(mapped=True),
                    inchi_key=molecule.to_inchikey(),
                )
            ]
        }
    )

    monkeypatch.setattr(
        OptimizationResultCollection,
        "to_records",
        lambda self: [qc_optimization_record],
    )

    return collection


@pytest.fixture(scope="module")
def qc_hessian_record() -> Tuple[ResultRecord, Molecule]:

    qc_client = FractalClient()

    [record] = qc_client.query_procedures(id="18854435")
    [qc_molecule] = qc_client.query_molecules(id="12121726")

    qc_molecule_dict = qc_molecule.dict(encoding="json")

    qc_molecule_dict["attributes"] = {
        "canonical_isomeric_explicit_hydrogen_mapped_smiles": (
            "[H:13][c:1]1[c:2]([c:4]([n:9][c:7]([c:3]1[H:15])[N:11]([H:19])[C:8]2="
            "[N:10][C:5](=[C:6]([O:12]2)[H:18])[H:17])[H:16])[H:14]"
        )
    }
    molecule = Molecule.from_qcschema(qc_molecule_dict)
    molecule.add_conformer(
        qc_molecule.geometry.reshape((molecule.n_atoms, 3)) * unit.bohr
    )

    return record, molecule


@pytest.fixture()
def qc_hessian_results(
    qc_hessian_record: ResultRecord, monkeypatch
) -> BasicResultCollection:

    _, molecule = qc_hessian_record

    collection = BasicResultCollection(
        entries={
            "http://localhost:442": [
                BasicResult(
                    record_id=ObjectId("1"),
                    cmiles=molecule.to_smiles(mapped=True),
                    inchi_key=molecule.to_inchikey(),
                )
            ]
        }
    )

    monkeypatch.setattr(
        OptimizationResultCollection,
        "to_records",
        lambda self: [qc_hessian_record],
    )

    return collection


@pytest.fixture()
def general_optimization_schema(
    qc_torsion_drive_results: TorsionDriveResultCollection,
    qc_optimization_results: OptimizationResultCollection,
    qc_hessian_results: BasicResultCollection,
    monkeypatch,
):

    optimization_schema = OptimizationSchema(
        initial_force_field="openff-1.3.0.offxml",
        optimizer=ForceBalanceSchema(),
        targets=[
            TorsionProfileTargetSchema(reference_data=qc_torsion_drive_results),
            AbInitioTargetSchema(reference_data=qc_torsion_drive_results),
            VibrationTargetSchema(reference_data=qc_hessian_results),
            OptGeoTargetSchema(reference_data=qc_optimization_results),
        ],
        parameter_settings=[ProperTorsionSettings()],
        target_parameters=[
            ProperTorsionSmirks(
                smirks="[*:1]-[#6X4:2]-[#6X4:3]-[*:4]", attributes={"k1"}
            )
        ],
    )

    return optimization_schema


@pytest.fixture()
def bespoke_optimization_schema() -> BespokeOptimizationSchema:
    """Create a workflow schema which targets the rotatable bond in ethane."""

    molecule = Molecule.from_smiles("c1ccc(cc1)c2cccc(c2)")

    schema_factory = BespokeWorkflowFactory(
        # turn off bespoke terms we want fast fitting
        generate_bespoke_terms=False,
        expand_torsion_terms=False,
        optimizer=ForceBalanceSchema(max_iterations=1, initial_trust_radius=0.25),
    )

    return schema_factory.optimization_schema_from_molecule(molecule)
