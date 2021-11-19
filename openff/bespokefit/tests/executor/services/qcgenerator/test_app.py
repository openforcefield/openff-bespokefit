import numpy
import pytest
from celery.result import AsyncResult
from openff.toolkit.topology import Molecule
from qcelemental.models import AtomicResult, AtomicResultProperties, DriverEnum
from qcelemental.models.common_models import Model, Provenance
from qcelemental.models.procedures import (
    OptimizationSpecification,
    QCInputSpecification,
    TDKeywords,
    TorsionDriveResult,
)

from openff.bespokefit.executor.services.qcgenerator import worker
from openff.bespokefit.executor.services.qcgenerator.app import _retrieve_qc_result
from openff.bespokefit.executor.services.qcgenerator.cache import _canonicalize_task
from openff.bespokefit.executor.services.qcgenerator.models import (
    QCGeneratorGETPageResponse,
    QCGeneratorGETResponse,
    QCGeneratorPOSTBody,
    QCGeneratorPOSTResponse,
)
from openff.bespokefit.executor.utilities.depiction import IMAGE_UNAVAILABLE_SVG
from openff.bespokefit.schema.tasks import HessianTask, OptimizationTask, Torsion1DTask
from openff.bespokefit.tests.executor.mocking.celery import mock_celery_task


@pytest.fixture()
def mock_atomic_result() -> AtomicResult:

    molecule: Molecule = Molecule.from_smiles("C")
    molecule.generate_conformers(n_conformers=1)

    return AtomicResult(
        molecule=molecule.to_qcschema(),
        driver=DriverEnum.hessian,
        model=Model(method="uff", basis=None),
        return_result=5.2,
        success=True,
        provenance=Provenance(creator="pytest"),
        properties=AtomicResultProperties(),
    )


@pytest.fixture()
def mock_torsion_drive_result() -> TorsionDriveResult:

    molecule: Molecule = Molecule.from_mapped_smiles("[H:1][C:2]#[C:3][H:4]")
    molecule.generate_conformers(n_conformers=1)

    return TorsionDriveResult(
        keywords=TDKeywords(dihedrals=[(0, 1, 2, 3)], grid_spacing=[15]),
        input_specification=QCInputSpecification(
            model=Model(method="uff", basis=None), driver=DriverEnum.gradient
        ),
        initial_molecule=[molecule.to_qcschema()],
        optimization_spec=OptimizationSpecification(procedure="geometric"),
        final_energies={"[180]": 1.0},
        final_molecules={"[180]": molecule.to_qcschema()},
        optimization_history={},
        success=True,
        provenance=Provenance(creator="pytest"),
    )


@pytest.mark.parametrize(
    "task_status, task_result, expected_state",
    [
        ("PENDING", {}, "waiting"),
        ("STARTED", {}, "running"),
        ("FAILURE", {"error_message": "error"}, "errored"),
    ],
)
def test_retrieve_qc_result_pending_running_errored(
    redis_connection, monkeypatch, task_status, task_result, expected_state
):

    monkeypatch.setattr(
        AsyncResult,
        "_get_task_meta",
        lambda self: {"status": task_status, "result": task_result},
    )
    redis_connection.hset("qcgenerator:types", "1", "torsion1d")

    result = QCGeneratorGETResponse.parse_obj(_retrieve_qc_result("1", True))

    assert result.status == expected_state
    assert result.result is None
    assert result.type == "torsion1d"
    assert result.id == "1"


def test_retrieve_qc_result_success(
    qcgenerator_client, redis_connection, monkeypatch, mock_atomic_result
):

    monkeypatch.setattr(
        AsyncResult,
        "_get_task_meta",
        lambda self: {"status": "SUCCESS", "result": mock_atomic_result.json()},
    )

    redis_connection.hset("qcgenerator:types", "1", "hessian")

    result = QCGeneratorGETResponse.parse_obj(_retrieve_qc_result("1", True))

    assert result.status == "success"
    assert result.result is not None
    assert result.type == "hessian"
    assert result.id == "1"

    assert result.result.driver == DriverEnum.hessian
    assert numpy.isclose(result.result.return_result, 5.2)


def test_get_qc_result(
    qcgenerator_client, redis_connection, monkeypatch, mock_atomic_result
):

    monkeypatch.setattr(
        AsyncResult,
        "_get_task_meta",
        lambda self: {"status": "SUCCESS", "result": mock_atomic_result.json()},
    )

    redis_connection.hset("qcgenerator:types", "1", "hessian")

    request = qcgenerator_client.get("/qc-calcs/1")
    request.raise_for_status()

    result = QCGeneratorGETResponse.parse_raw(request.text)

    assert result.status == "success"
    assert result.result is not None
    assert result.type == "hessian"
    assert result.id == "1"
    assert result.self == "/api/v1/qc-calcs/1"

    assert result.result.driver == DriverEnum.hessian
    assert numpy.isclose(result.result.return_result, 5.2)


@pytest.mark.parametrize(
    "task, compute_function",
    [
        (
            Torsion1DTask(
                smiles="[CH2:1][CH2:2]",
                central_bond=(1, 2),
                program="rdkit",
                model=Model(method="uff", basis=None),
            ),
            "compute_torsion_drive",
        ),
        (
            OptimizationTask(
                smiles="[CH2:1][CH2:2]",
                n_conformers=1,
                program="rdkit",
                model=Model(method="uff", basis=None),
            ),
            "compute_optimization",
        ),
        (
            HessianTask(
                smiles="[CH2:1][CH2:2]",
                program="rdkit",
                model=Model(method="uff", basis=None),
            ),
            "compute_hessian",
        ),
    ],
)
def test_post_qc_result(
    qcgenerator_client, redis_connection, monkeypatch, task, compute_function
):

    submitted_task_kwargs = mock_celery_task(worker, compute_function, monkeypatch)

    request = qcgenerator_client.post(
        "/qc-calcs", data=QCGeneratorPOSTBody(input_schema=task).json()
    )
    request.raise_for_status()

    assert submitted_task_kwargs["task_json"] == _canonicalize_task(task).json()
    assert redis_connection.hget("qcgenerator:types", "1").decode() == task.type

    result = QCGeneratorPOSTResponse.parse_raw(request.text)
    assert result.id == "1"
    assert result.self == "/api/v1/qc-calcs/1"


@pytest.mark.parametrize("include_result", [True, False])
def test_get_qc_results(
    qcgenerator_client,
    redis_connection,
    monkeypatch,
    mock_atomic_result,
    include_result,
):

    monkeypatch.setattr(
        AsyncResult,
        "_get_task_meta",
        lambda self: {"status": "SUCCESS", "result": mock_atomic_result.json()},
    )

    redis_connection.hset("qcgenerator:types", "1", "hessian")
    redis_connection.hset("qcgenerator:types", "2", "hessian")

    request = qcgenerator_client.get(
        f"/qc-calcs?ids=1&ids=2&results={str(include_result).lower()}"
    )
    request.raise_for_status()

    response = QCGeneratorGETPageResponse.parse_raw(request.text)
    assert len(response.contents) == 2

    for i, result in enumerate(response.contents):

        assert result.status == "success"
        assert (result.result is not None) == include_result
        assert result.type == "hessian"
        assert result.id == f"{i + 1}"


def test_get_molecule_image_atomic_result(
    qcgenerator_client, redis_connection, monkeypatch, mock_atomic_result
):
    monkeypatch.setattr(
        AsyncResult,
        "_get_task_meta",
        lambda self: {"status": "SUCCESS", "result": mock_atomic_result.json()},
    )
    redis_connection.hset("qcgenerator:types", "1", "hessian")

    request = qcgenerator_client.get("/qc-calcs/1/image/molecule")
    request.raise_for_status()

    assert "<svg" in request.text
    assert request.headers["content-type"] == "image/svg+xml"


def test_get_molecule_image_torsion_drive(
    qcgenerator_client, redis_connection, monkeypatch, mock_torsion_drive_result
):

    monkeypatch.setattr(
        AsyncResult,
        "_get_task_meta",
        lambda self: {"status": "SUCCESS", "result": mock_torsion_drive_result.json()},
    )
    redis_connection.hset("qcgenerator:types", "1", "torsion1d")

    request = qcgenerator_client.get("/qc-calcs/1/image/molecule")
    request.raise_for_status()

    assert "<svg" in request.text
    assert request.headers["content-type"] == "image/svg+xml"


def test_get_molecule_image_pending(
    qcgenerator_client, redis_connection, monkeypatch, mock_torsion_drive_result
):
    monkeypatch.setattr(
        AsyncResult,
        "_get_task_meta",
        lambda self: {"status": "PENDING", "result": None},
    )

    request = qcgenerator_client.get("/qc-calcs/1/image/molecule")
    request.raise_for_status()

    assert request.text == IMAGE_UNAVAILABLE_SVG
    assert request.headers["content-type"] == "image/svg+xml"
