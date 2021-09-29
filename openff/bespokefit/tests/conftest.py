import json
from typing import Tuple

import pytest
from openff.fragmenter.fragment import Fragment, FragmentationResult
from openff.qcsubmit.results import (
    BasicResult,
    BasicResultCollection,
    OptimizationResult,
    OptimizationResultCollection,
    TorsionDriveResult,
    TorsionDriveResultCollection,
)
from openff.toolkit.topology import Molecule
from qcelemental.models import AtomicResult
from qcelemental.models.common_models import Model, Provenance
from qcelemental.models.procedures import OptimizationResult as QCOptimizationResult
from qcelemental.models.procedures import (
    OptimizationSpecification,
    QCInputSpecification,
)
from qcelemental.models.procedures import TorsionDriveResult as QCTorsionDriveResult
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
from openff.bespokefit.schema.smirnoff import (
    ProperTorsionHyperparameters,
    ProperTorsionSMIRKS,
)
from openff.bespokefit.schema.targets import (
    AbInitioTargetSchema,
    OptGeoTargetSchema,
    TorsionProfileTargetSchema,
    VibrationTargetSchema,
)
from openff.bespokefit.workflows.bespoke import BespokeWorkflowFactory


@pytest.fixture(scope="function", autouse=True)
def clear_force_balance_caches():
    """A fixture which will clean the incredibly bug prone ``smirnoff_hack`` caches prior
    to each test running."""

    from forcebalance.smirnoff_hack import (
        AT_TOOLKIT_CACHE_assign_partial_charges,
        OE_TOOLKIT_CACHE_assign_partial_charges,
        OE_TOOLKIT_CACHE_find_smarts_matches,
        OE_TOOLKIT_CACHE_molecule_conformers,
        RDK_TOOLKIT_CACHE_find_smarts_matches,
        RDK_TOOLKIT_CACHE_molecule_conformers,
        TOOLKIT_CACHE_ChemicalEnvironment_validate,
    )

    OE_TOOLKIT_CACHE_find_smarts_matches.clear()
    RDK_TOOLKIT_CACHE_find_smarts_matches.clear()
    TOOLKIT_CACHE_ChemicalEnvironment_validate.clear()
    OE_TOOLKIT_CACHE_assign_partial_charges.clear()
    AT_TOOLKIT_CACHE_assign_partial_charges.clear()
    OE_TOOLKIT_CACHE_molecule_conformers.clear()
    RDK_TOOLKIT_CACHE_molecule_conformers.clear()


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


@pytest.fixture()
def qc_torsion_drive_qce_result(
    qc_torsion_drive_record,
) -> Tuple[QCTorsionDriveResult, Molecule]:

    qc_record, molecule = qc_torsion_drive_record

    qc_result = QCTorsionDriveResult(
        keywords=qc_record.keywords,
        extras={
            "id": qc_record.id,
            "canonical_isomeric_explicit_hydrogen_mapped_smiles": molecule.to_smiles(
                isomeric=True, explicit_hydrogens=True, mapped=True
            ),
        },
        input_specification=QCInputSpecification(
            driver=qc_record.qc_spec.driver,
            model=Model(method=qc_record.qc_spec.method, basis=qc_record.qc_spec.basis),
        ),
        initial_molecule=molecule.to_qcschema(),
        optimization_spec=OptimizationSpecification(
            procedure=qc_record.optimization_spec.program,
            keywords=qc_record.optimization_spec.keywords,
        ),
        final_energies={
            json.dumps(key): value
            for key, value in qc_record.get_final_energies().items()
        },
        final_molecules={
            grid_id: molecule.to_qcschema(conformer=i)
            for grid_id, i in zip(
                molecule.properties["grid_ids"], range(len(molecule.conformers))
            )
        },
        optimization_history={},
        provenance=Provenance(creator="fixture"),
        success=True,
    )

    return qc_result, molecule


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


@pytest.fixture()
def qc_optimization_qce_result(
    qc_optimization_record,
) -> Tuple[QCOptimizationResult, Molecule]:

    qc_record, molecule = qc_optimization_record

    qc_result = QCOptimizationResult(
        keywords=qc_record.keywords,
        extras={
            "id": qc_record.id,
            "canonical_isomeric_explicit_hydrogen_mapped_smiles": molecule.to_smiles(
                isomeric=True, explicit_hydrogens=True, mapped=True
            ),
        },
        input_specification=QCInputSpecification(
            driver=qc_record.qc_spec.driver,
            model=Model(method=qc_record.qc_spec.method, basis=qc_record.qc_spec.basis),
        ),
        initial_molecule=molecule.to_qcschema(),
        energies=qc_record.energies,
        final_molecule=molecule.to_qcschema(),
        trajectory=[],
        provenance=Provenance(creator="fixture"),
        success=True,
    )

    return qc_result, molecule


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
        BasicResultCollection,
        "to_records",
        lambda self: [qc_hessian_record],
    )

    return collection


@pytest.fixture()
def qc_hessian_qce_result(
    qc_hessian_record,
) -> Tuple[AtomicResult, Molecule]:

    qc_record, molecule = qc_hessian_record

    qc_result = AtomicResult(
        extras={
            "id": qc_record.id,
            "canonical_isomeric_explicit_hydrogen_mapped_smiles": molecule.to_smiles(
                isomeric=True, explicit_hydrogens=True, mapped=True
            ),
            **qc_record.extras,
        },
        properties=qc_record.properties,
        molecule=molecule.to_qcschema(),
        driver=qc_record.driver,
        model=Model(method=qc_record.method, basis=qc_record.basis),
        return_result=qc_record.return_result,
        provenance=Provenance(creator="fixture"),
        success=True,
    )

    return qc_result, molecule


@pytest.fixture()
def general_optimization_schema(
    qc_torsion_drive_results: TorsionDriveResultCollection,
    qc_optimization_results: OptimizationResultCollection,
    qc_hessian_results: BasicResultCollection,
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
        parameter_hyperparameters=[ProperTorsionHyperparameters()],
        parameters=[
            ProperTorsionSMIRKS(
                smirks="[*:1]-[#6X4:2]-[#6X4:3]-[*:4]", attributes={"k1"}
            )
        ],
    )

    return optimization_schema


@pytest.fixture(scope="session")
def bespoke_optimization_schema() -> BespokeOptimizationSchema:
    """Create a workflow schema which targets the rotatable bond in biphenyl."""

    molecule = Molecule.from_smiles("c1ccc(cc1)c2cccc(c2)")

    schema_factory = BespokeWorkflowFactory(
        # turn off bespoke terms we want fast fitting
        generate_bespoke_terms=False,
        expand_torsion_terms=False,
        optimizer=ForceBalanceSchema(max_iterations=1, initial_trust_radius=0.25),
    )

    return schema_factory.optimization_schema_from_molecule(molecule)


@pytest.fixture()
def bace_fragment_data() -> FragmentationResult:
    """
    Create a fragment data object for a bace parent and fragment.
    """

    return FragmentationResult(
        parent_smiles="[H:24][c:1]1[c:3]([c:9]([c:7]([c:11]([c:5]1[H:28])[C@@:15]2("
        "[C:13](=[O:22])[N:19]([C:14](=[N+:20]2[H:40])[N:21]([H:41])[H:42])[C:17]"
        "([H:35])([H:36])[H:37])[C:18]([H:38])([H:39])[C:16]([H:32])([H:33])[H:34])"
        "[H:30])[c:10]3[c:4]([c:2]([c:6]([c:12]([c:8]3[H:31])[Cl:23])[H:29])[H:25])"
        "[H:27])[H:26]",
        fragments=[
            Fragment(
                smiles="[H:28][c:5]1[c:1]([c:3]([c:9]([c:7]([c:11]1[H])[H:30])[c:10]2"
                "[c:4]([c:2]([c:6]([c:12]([c:8]2[H:31])[H])[H:29])[H:25])[H:27])[H:26])"
                "[H:24]",
                bond_indices=(9, 10),
            )
        ],
        provenance={},
    )
