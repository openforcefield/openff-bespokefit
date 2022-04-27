import datetime
import hashlib
import json
import logging
import uuid
from multiprocessing import Pool
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import psutil
import qcelemental
import qcengine
from celery.utils.log import get_task_logger
from openff.toolkit.topology import Atom, Molecule
from qcelemental.models import AtomicInput, AtomicResult
from qcelemental.models.common_models import DriverEnum
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
from openff.bespokefit.executor.services.qcgenerator.qcengine import _divide_config
from openff.bespokefit.executor.utilities.celery import configure_celery_app
from openff.bespokefit.executor.utilities.redis import connect_to_default_redis
from openff.bespokefit.schema.tasks import (
    OptimizationTask,
    QCGenerationTask,
    Torsion1DTask,
)

if TYPE_CHECKING:
    from redis import Redis

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


def _load_cached_torsiondrive(
    redis_connection: "Redis", task_hash: str
) -> Optional[TorsionDriveResult]:
    """
    Try and load a cached torsiondrive from the redis connection
    """
    td_result = None
    task_id = redis_connection.hget("qcgenerator:task-ids", task_hash)
    if task_id is not None:
        task_id = task_id.decode()
        _task_logger.info(f"found cached torsiondrive with id:{task_id}")
        task_meta = json.loads(redis_connection.get(f"celery-task-meta-{task_id}"))
        td_result = TorsionDriveResult.parse_raw(task_meta["result"])

    return td_result


@celery_app.task(acks_late=True)
def compute_torsion_drive(task_json: str) -> TorsionDriveResult:
    """Runs a torsion drive using QCEngine."""

    task = Torsion1DTask.parse_raw(task_json)

    return_value = None
    # look up the geometry optimisation
    # here we drop the single point specification and search
    sp_specification = (
        task.sp_specification.copy(deep=True)
        if task.sp_specification is not None
        else None
    )
    task.sp_specification = None
    redis_connection = connect_to_default_redis()
    task_hash = hashlib.sha512(task.json().encode()).hexdigest()

    # only look up if there is a sp specification otherwise we get back this task
    if sp_specification is not None:
        return_value = _load_cached_torsiondrive(
            redis_connection=redis_connection, task_hash=task_hash
        )

    if return_value is None:
        # run the geometry optimisation if not in the cache
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
                dihedral_ranges=[task.scan_range]
                if task.scan_range is not None
                else None,
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
            input_schema,
            "torsiondriveparallel",
            raise_error=True,
            local_options=_task_config(),
        )

        if isinstance(return_value, TorsionDriveResult):

            return_value = TorsionDriveResult(
                **return_value.dict(
                    exclude={"optimization_history", "stdout", "stderr"}
                ),
                optimization_history={},
            )
        # cache the result of the geometry optimisation only if there is a single point spec
        if sp_specification is not None:
            task_id = str(uuid.uuid4())
            redis_connection.hset("qcgenerator:types", task_id, task.type)
            redis_connection.hset("qcgenerator:task-ids", task_hash, task_id)
            # mock a result
            task_meta = {
                "status": "SUCCESS",
                "result": return_value.json(),
                "traceback": None,
                "children": [],
                "date_done": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"),
                "task_id": task_id,
            }
            redis_connection.set(f"celery-task-meta-{task_id}", json.dumps(task_meta))
            _task_logger.info(f"caching torsiondrive result {task_id}")

    # check if we need to do single points
    if sp_specification is not None:
        # no need for final cache as this is saved at the top level
        return_value = _compute_torsiondrive_sp(
            torsiondrive_result=return_value,
            torsion_specification=sp_specification,
            config=_task_config(),
        )

    # noinspection PyTypeChecker
    return return_value.json()


def _compute_torsiondrive_sp(
    torsiondrive_result: TorsionDriveResult,
    torsion_specification: QCGenerationTask,
    config: Dict[str, Any],
) -> TorsionDriveResult:
    """
    Compute single points along the final optimised geometries from a torsion drive using the single point specification
    on the task.
    """
    _task_logger.info(
        f"performing single point evaluations using {torsion_specification}"
    )
    settings = current_settings()
    program = torsion_specification.program
    n_workers = settings.BEFLOW_QC_COMPUTE_WORKER_N_TASKS
    config["retries"] = 4
    if program == "psi4" and n_workers == "auto":
        # we recommend 8 cores per worker for psi4 from our qcfractal jobs
        n_workers = max([int(config["ncores"] / 8), 1])
    elif n_workers == "auto":
        # for low cost methods like ani or xtb they are fast enough to not need splitting
        n_workers = 1

    opt_config = _divide_config(
        config=qcengine.config.TaskConfig.parse_obj(config), n_workers=n_workers
    )

    if n_workers > 1:
        # split the tasks between a pool of workers
        with Pool(processes=n_workers) as pool:
            tasks = {
                grid_point: pool.apply_async(
                    func=_single_point,
                    args=(molecule, torsion_specification, opt_config),
                )
                for grid_point, molecule in torsiondrive_result.final_molecules.items()
            }
            energies = {
                grid_point: result.get() for grid_point, result in tasks.items()
            }
    else:
        energies = {
            grid_point: _single_point(
                molecule=molecule,
                specification=torsion_specification,
                config=opt_config.dict(),
            ).return_result
            for grid_point, molecule in torsiondrive_result.final_molecules.items()
        }
    # format into a result
    final_result = torsiondrive_result.copy(deep=True)
    for grid_point, energy in energies.items():
        final_result.final_energies[grid_point] = energy
    return final_result


def _single_point(
    molecule: qcelemental.models.Molecule,
    specification: QCGenerationTask,
    config: Dict[str, Any],
) -> AtomicResult:
    """
    Perform a single point calculation on the input qcelemental molecule.
    """
    sp_task = AtomicInput(
        molecule=molecule, driver=DriverEnum.energy, model=specification.model
    )
    return qcengine.compute(
        input_data=sp_task,
        program=specification.program,
        raise_error=True,
        local_options=config,
    )


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
