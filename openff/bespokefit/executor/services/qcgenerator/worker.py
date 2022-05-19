import logging
from typing import Any, Dict, List

import psutil
import qcelemental
import qcengine
from celery import Task
from celery.utils.log import get_task_logger
from openff.toolkit.topology import Atom, Molecule
from qcelemental.models import AtomicInput, AtomicResult
from qcelemental.models.common_models import DriverEnum, Model, Provenance
from qcelemental.models.procedures import (
    OptimizationInput,
    OptimizationResult,
    OptimizationSpecification,
    QCInputSpecification,
    TDKeywords,
    TorsionDriveInput,
    TorsionDriveResult,
)
from qcelemental.util import serialize
from qcengine.config import get_global

from openff.bespokefit.executor.services import current_settings
from openff.bespokefit.executor.utilities.celery import configure_celery_app
from openff.bespokefit.executor.utilities.redis import connect_to_default_redis
from openff.bespokefit.schema.tasks import OptimizationTask, Torsion1DTask

celery_app = configure_celery_app(
    "qcgenerator", connect_to_default_redis(validate=False)
)

_task_logger: logging.Logger = get_task_logger(__name__)


def _task_config() -> Dict[str, Any]:

    worker_settings = current_settings().qc_compute_settings

    n_cores = (
        get_global("ncores") if not worker_settings.n_cores else worker_settings.n_cores
    )
    max_memory = (
        (psutil.virtual_memory().total / (1024**3))
        if not worker_settings.max_memory
        else (
            worker_settings.max_memory
            * qcelemental.constants.conversion_factor("gigabyte", "gibibyte")
            * n_cores
        )
    )

    return dict(ncores=n_cores, nnodes=1, memory=round(max_memory, 3))


def _select_atom(atoms: List[Atom]) -> int:
    """
    For a list of atoms chose the heaviest atom.
    """
    candidate = atoms[0]
    for atom in atoms:
        if atom.atomic_number > candidate.atomic_number:
            candidate = atom
    return candidate.molecule_atom_index


@celery_app.task(acks_late=True)
def compute_torsion_drive(task_json: str) -> str:
    """Runs a torsion drive using QCEngine."""

    task = Torsion1DTask.parse_raw(task_json)

    _task_logger.info(f"running 1D scan with {_task_config()}")

    molecule: Molecule = Molecule.from_smiles(task.smiles)
    molecule.generate_conformers(n_conformers=task.n_conformers)

    map_to_atom_index = {
        map_index: atom_index
        for atom_index, map_index in molecule.properties["atom_map"].items()
    }

    index_2 = map_to_atom_index[task.central_bond[0]]
    index_3 = map_to_atom_index[task.central_bond[1]]

    index_1_atoms = [
        atom
        for atom in molecule.atoms[index_2].bonded_atoms
        if atom.molecule_atom_index != index_3
    ]
    index_4_atoms = [
        atom
        for atom in molecule.atoms[index_3].bonded_atoms
        if atom.molecule_atom_index != index_2
    ]

    del molecule.properties["atom_map"]

    input_schema = TorsionDriveInput(
        keywords=TDKeywords(
            dihedrals=[
                (
                    _select_atom(index_1_atoms),
                    index_2,
                    index_3,
                    _select_atom(index_4_atoms),
                )
            ],
            grid_spacing=[task.grid_spacing],
            dihedral_ranges=[task.scan_range] if task.scan_range is not None else None,
        ),
        extras={
            "canonical_isomeric_explicit_hydrogen_mapped_smiles": molecule.to_smiles(
                isomeric=True, explicit_hydrogens=True, mapped=True
            )
        },
        initial_molecule=[
            molecule.to_qcschema(conformer=i) for i in range(molecule.n_conformers)
        ],
        input_specification=QCInputSpecification(
            model=task.model,
            driver=DriverEnum.gradient,
        ),
        optimization_spec=OptimizationSpecification(
            procedure=task.optimization_spec.program,
            keywords={
                **task.optimization_spec.dict(exclude={"program", "constraints"}),
                "program": task.program,
            },
        ),
    )

    return_value = qcengine.compute_procedure(
        input_schema, "torsiondrive", raise_error=True, local_options=_task_config()
    )

    if isinstance(return_value, TorsionDriveResult):

        return_value = TorsionDriveResult(
            **return_value.dict(exclude={"optimization_history", "stdout", "stderr"}),
            optimization_history={},
        )

    return return_value.json()


@celery_app.task(acks_late=True)
def evaluate_torsion_drive(
    result_json: str,
    model: Model,
    program: str,
) -> TorsionDriveResult:
    """
    Re-evaluates the energies at each optimised geometry along a torsion drive
    at a new level of theory.
    """

    _task_logger.info(
        f"performing single point evaluations using {model} and {program}"
    )

    original_result = TorsionDriveResult.parse_raw(result_json)

    qcengine_config = _task_config()
    qcengine_config["retries"] = 4  # TODO: expose via env. variable

    energies = {
        grid_point: _compute_single_point(
            molecule=molecule,
            model=model,
            program=program,
            config=qcengine_config,
        ).return_result
        for grid_point, molecule in original_result.final_molecules.items()
    }

    final_result = TorsionDriveResult(
        keywords=original_result.keywords,
        extras=original_result.extras,
        input_specification=QCInputSpecification(driver=DriverEnum.energy, model=model),
        initial_molecule=original_result.initial_molecule,
        optimization_spec=original_result.optimization_spec,
        final_energies=energies,
        final_molecules=original_result.final_molecules,
        optimization_history={},
        success=True,
        provenance=Provenance(
            creator="openff-bespokefit", routine="evaluate_torsion_drive"
        ),
    )

    return final_result


@celery_app.task
def compute_optimization(
    task_json: str,
) -> List[OptimizationResult]:
    """Runs a set of geometry optimizations using QCEngine."""
    # TODO: should we only return the lowest energy optimization?
    # or the first optimisation to work?

    task = OptimizationTask.parse_raw(task_json)

    _task_logger.info(f"running opt with {_task_config()}")

    molecule: Molecule = Molecule.from_smiles(task.smiles)
    molecule.generate_conformers(n_conformers=task.n_conformers)

    input_schemas = [
        OptimizationInput(
            keywords={
                **task.optimization_spec.dict(exclude={"program", "constraints"}),
                "program": task.program,
            },
            extras={
                "canonical_isomeric_explicit_hydrogen_mapped_smiles": molecule.to_smiles(
                    isomeric=True, explicit_hydrogens=True, mapped=True
                )
            },
            input_specification=QCInputSpecification(
                model=task.model,
                driver=DriverEnum.gradient,
            ),
            initial_molecule=molecule.to_qcschema(conformer=i),
        )
        for i in range(molecule.n_conformers)
    ]

    return_values = []

    for input_schema in input_schemas:

        return_value = qcengine.compute_procedure(
            input_schema,
            task.optimization_spec.program,
            raise_error=True,
            local_options=_task_config(),
        )

        if isinstance(return_value, OptimizationResult):

            # Strip the extra **heavy** data
            return_value = OptimizationResult(
                **return_value.dict(exclude={"trajectory", "stdout", "stderr"}),
                trajectory=[],
            )

        return_values.append(return_value)

    # noinspection PyTypeChecker
    return serialize(return_values, "json")


@celery_app.task
def compute_hessian(task_json: str) -> AtomicResult:
    """Runs a set of hessian evaluations using QCEngine."""
    raise NotImplementedError()


def _compute_single_point(
    molecule: qcelemental.models.Molecule,
    model: Model,
    program: str,
    config: Dict[str, Any],
) -> AtomicResult:
    """
    Perform a single point calculation on the input ``qcelemental`` molecule.
    """

    qc_input = AtomicInput(molecule=molecule, driver=DriverEnum.energy, model=model)
    return qcengine.compute(
        input_data=qc_input,
        program=program,
        raise_error=True,
        local_options=config,
    )


@celery_app.task(bind=True, max_retries=None, ignore_result=True)
def wait_for_task(self: Task, task_id, interval=10):

    result = celery_app.AsyncResult(task_id)

    if result.failed():
        result.throw()
    elif not result.ready():
        self.retry(countdown=interval)
