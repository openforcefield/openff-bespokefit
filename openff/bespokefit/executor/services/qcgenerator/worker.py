from typing import List

import qcengine
import redis
from openff.toolkit.topology import Molecule
from qcelemental.models import AtomicResult
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

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.utilities.celery import configure_celery_app
from openff.bespokefit.schema.tasks import OptimizationTask, Torsion1DTask

redis_connection = redis.Redis(
    host=settings.BEFLOW_REDIS_ADDRESS,
    port=settings.BEFLOW_REDIS_PORT,
    db=settings.BEFLOW_REDIS_DB,
)
celery_app = configure_celery_app("qcgenerator", redis_connection)


@celery_app.task(acks_late=True)
def compute_torsion_drive(task_json: str) -> TorsionDriveResult:
    """Runs a torsion drive using QCEngine."""

    task = Torsion1DTask.parse_raw(task_json)

    molecule: Molecule = Molecule.from_smiles(task.smiles)
    # TODO: Ask Josh about multiple conformers.
    molecule.generate_conformers(n_conformers=1)

    map_to_atom_index = {
        map_index: atom_index
        for atom_index, map_index in molecule.properties["atom_map"].items()
    }

    index_2 = map_to_atom_index[task.central_bond[0]]
    index_3 = map_to_atom_index[task.central_bond[1]]

    index_1 = [
        atom.molecule_atom_index
        for atom in molecule.atoms[index_2].bonded_atoms
        if atom.molecule_atom_index != index_3
    ][0]
    index_4 = [
        atom.molecule_atom_index
        for atom in molecule.atoms[index_3].bonded_atoms
        if atom.molecule_atom_index != index_2
    ][0]

    del molecule.properties["atom_map"]

    input_schema = TorsionDriveInput(
        keywords=TDKeywords(
            dihedrals=[(index_1, index_2, index_3, index_4)],
            grid_spacing=[task.grid_spacing],
            dihedral_ranges=[task.scan_range],
        ),
        extras={
            "canonical_isomeric_explicit_hydrogen_mapped_smiles": molecule.to_smiles(
                isomeric=True, explicit_hydrogens=True, mapped=True
            )
        },
        initial_molecule=molecule.to_qcschema(),
        input_specification=QCInputSpecification(
            model=task.model, driver=DriverEnum.gradient
        ),
        optimization_spec=OptimizationSpecification(
            procedure=task.optimization_spec.procedure,
            keywords={
                "coordsys": "dlc",
                "maxiter": task.optimization_spec.max_iterations,
                "program": task.program,
            },
        ),
    )

    return_value = qcengine.compute_procedure(
        input_schema, "torsiondrive", raise_error=True
    )

    if isinstance(return_value, TorsionDriveResult):

        return_value = TorsionDriveResult(
            **return_value.dict(exclude={"optimization_history", "stdout", "stderr"}),
            optimization_history={},
        )

    # noinspection PyTypeChecker
    return return_value.json()


@celery_app.task
def compute_optimization(
    task_json: str,
) -> List[OptimizationResult]:
    """Runs a set of geometry optimizations using QCEngine."""

    task = OptimizationTask.parse_raw(task_json)

    molecule: Molecule = Molecule.from_smiles(task.smiles)
    molecule.generate_conformers(n_conformers=task.n_conformers)

    input_schemas = [
        OptimizationInput(
            keywords={
                "coordsys": "dlc",
                "maxiter": task.optimization_spec.max_iterations,
                "program": task.program,
            },
            extras={
                "canonical_isomeric_explicit_hydrogen_mapped_smiles": molecule.to_smiles(
                    isomeric=True, explicit_hydrogens=True, mapped=True
                )
            },
            input_specification=QCInputSpecification(
                model=task.model, driver=DriverEnum.gradient
            ),
            initial_molecule=molecule.to_qcschema(conformer=i),
        )
        for i in range(molecule.n_conformers)
    ]

    return_values = []

    for input_schema in input_schemas:

        return_value = qcengine.compute_procedure(
            input_schema, task.optimization_spec.procedure, raise_error=True
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
