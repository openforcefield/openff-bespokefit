import abc
import copy
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Generic, List, Tuple, TypeVar, Union

import numpy as np
from openff.qcsubmit.results import (
    BasicResultCollection,
    OptimizationResultCollection,
    TorsionDriveResultCollection,
)
from openff.toolkit.topology import Molecule
from openff.toolkit.topology import Molecule as OFFMolecule
from openff.utilities import temporary_cd
from qcelemental.models import AtomicResult
from qcelemental.models.procedures import OptimizationResult, TorsionDriveResult
from qcportal.models import TorsionDriveRecord
from qcportal.models.records import OptimizationRecord, RecordBase, ResultRecord
from simtk import unit
from tqdm import tqdm

from openff.bespokefit.exceptions import OptimizerError, QCRecordMissMatchError
from openff.bespokefit.optimizers.forcebalance.templates import (
    AbInitioTargetTemplate,
    InputOptionsTemplate,
    OptGeoOptionsTemplate,
    OptGeoTargetTemplate,
    TorsionProfileTargetTemplate,
    VibrationTargetTemplate,
)
from openff.bespokefit.schema.data import BespokeQCData, LocalQCData
from openff.bespokefit.schema.fitting import BaseOptimizationSchema
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.targets import (
    AbInitioTargetSchema,
    OptGeoTargetSchema,
    TargetSchema,
    TorsionProfileTargetSchema,
    VibrationTargetSchema,
)

if TYPE_CHECKING:
    from qcelemental.models import Molecule as QCMolecule

logger = logging.getLogger(__name__)

R = TypeVar("R", bound=Union[AtomicResult, OptimizationResult, TorsionDriveResult])
S = TypeVar("S", bound=RecordBase)
T = TypeVar("T", bound=TargetSchema)

_TARGET_SECTION_TEMPLATES = {
    AbInitioTargetSchema: AbInitioTargetTemplate,
    TorsionProfileTargetSchema: TorsionProfileTargetTemplate,
    OptGeoTargetSchema: OptGeoTargetTemplate,
    VibrationTargetSchema: VibrationTargetTemplate,
}


def _standardize_grid_id_str(grid_id: str) -> str:
    """Ensures a grid id is of the form '[grid_id_1, ...]' rather than 'grid_id_1' as is
    sometimes the case when using QCEngine.
    """

    grid_id = json.loads(grid_id)
    grid_id = [grid_id] if isinstance(grid_id, int) else grid_id

    return json.dumps(grid_id)


class _TargetFactory(Generic[T], abc.ABC):
    @classmethod
    @abc.abstractmethod
    def _target_name_prefix(cls) -> str:
        raise NotImplementedError()

    @classmethod
    def _section_extras_to_exclude(cls) -> List[str]:
        """The list of extras which may be present in a target schemas ``.extras``
        dictionary to exclude when generating the section to add to the ``optimize.in``
        file."""
        return []

    @classmethod
    def _generate_targets_section(cls, target_template: T, target_names: List[str]):
        """Creates the target sections which will need to be added to the main
        ForceBalance 'options.in' file."""

        target_template = target_template.copy(deep=True)
        target_template.extras = {
            key: value
            for key, value in target_template.extras.items()
            if key not in cls._section_extras_to_exclude()
        }

        template_factory = _TARGET_SECTION_TEMPLATES[target_template.__class__]
        return template_factory.generate(target_template, target_names)

    @classmethod
    def _batch_qc_records(
        cls, target: TargetSchema, qc_records: List[Tuple[RecordBase, Molecule]]
    ) -> Dict[str, List[Tuple[RecordBase, Molecule]]]:
        """A function which places the input QC records into per target batches.

        For most targets there will be a single record per target, however certain
        targets (e.g. OptGeo) can perform on batches to reduce the time taken to
        evaluate the target.

        Args:
            target: The target the inputs are being generated for.
            qc_records: The QC records to batch

        Returns:
            A dictionary of the target name and a list of the records to include for that
            target.
        """

        def qc_record_id(qc_record):
            return qc_record.extras["id"] if "id" in qc_record.extras else qc_record.id

        return {
            f"{cls._target_name_prefix()}-{qc_record_id(qc_record)}": [
                (qc_record, molecule)
            ]
            for qc_record, molecule in qc_records
        }

    @classmethod
    @abc.abstractmethod
    def _generate_target(cls, target: T, qc_records: List[Tuple[RecordBase, Molecule]]):
        """Create the required input files for a particular target.

        Notes:
            * This function assumes that the files should be created in the current
              working directory.
        """
        raise NotImplementedError()

    @classmethod
    def _local_to_qc_records(cls, qc_data: LocalQCData[R]) -> List[Tuple[R, Molecule]]:
        """Converts a 'local' dataset of QCEngine outputs to a list of QC records."""
        qc_records = []

        for i, qc_result in enumerate(qc_data.qc_records):

            qc_result = qc_result.copy(deep=True)
            # Assign an id to the **QCElemental** result. This is a dirty way to do
            # this but I can't think of a cleaner way to handle it...
            qc_result.extras["id"] = str(i)

            grid_ids = None

            if isinstance(qc_result, AtomicResult):

                cmiles = qc_result.molecule.extras[
                    "canonical_isomeric_explicit_hydrogen_mapped_smiles"
                ]
                geometries = [qc_result.molecule.geometry]

            elif isinstance(qc_result, OptimizationResult):

                cmiles = qc_result.initial_molecule.extras[
                    "canonical_isomeric_explicit_hydrogen_mapped_smiles"
                ]
                geometries = [qc_result.final_molecule.geometry]

            elif isinstance(qc_result, TorsionDriveResult):

                cmiles = qc_result.initial_molecule.extras[
                    "canonical_isomeric_explicit_hydrogen_mapped_smiles"
                ]

                geometries = []
                grid_ids = []

                for grid_id, qc_molecule in qc_result.final_molecules.items():

                    grid_ids.append(_standardize_grid_id_str(grid_id))
                    geometries.append(qc_molecule.geometry)

            else:
                raise NotImplementedError()

            molecule: Molecule = Molecule.from_mapped_smiles(cmiles)
            molecule._conformers = [
                np.array(geometry, float).reshape(-1, 3) * unit.bohr
                for geometry in geometries
            ]

            if grid_ids is not None:
                molecule.properties["grid_ids"] = grid_ids

            qc_records.append((qc_result, molecule))

        return qc_records

    @classmethod
    def generate(cls, root_directory: Union[str, Path], target: T):
        """Creates the input files for a target schema in a specified directory.

        Args:
            root_directory: The root directory to create the inputs in.
            target: The target to create the inputs for. A single target schema may map
                to several new ForceBalance targets, typically one per QC record
                referenced by the schema.
        """

        # The optimizer should have swapped out a bespoke QC data set
        # with an existing set?
        if isinstance(
            target.reference_data,
            (
                BasicResultCollection,
                OptimizationResultCollection,
                TorsionDriveResultCollection,
            ),
        ):

            qc_records = target.reference_data.to_records()

        elif isinstance(target.reference_data, BespokeQCData):

            qc_records = [
                (task.reference_data.record, task.reference_data.molecule)
                for task in target.reference_data.tasks
            ]

        elif isinstance(target.reference_data, LocalQCData):

            qc_records = cls._local_to_qc_records(target.reference_data)

        else:
            raise NotImplementedError()

        target_batches = cls._batch_qc_records(target, qc_records)

        for target_name, target_records in tqdm(target_batches.items()):

            tqdm.write(f"generating target directory for {target_name}")

            target_directory = os.path.join(root_directory, target_name)
            os.makedirs(target_directory, exist_ok=True)

            with temporary_cd(target_directory):
                cls._generate_target(target, target_records)

        return cls._generate_targets_section(target, [*target_batches])


class AbInitioTargetFactory(_TargetFactory[AbInitioTargetSchema]):
    @classmethod
    def _target_name_prefix(cls) -> str:
        return "ab-initio"

    @classmethod
    def _generate_target(
        cls,
        target: T,
        qc_records: List[
            Tuple[Union[TorsionDriveRecord, TorsionDriveResult], Molecule]
        ],
    ):

        from forcebalance.molecule import Molecule as FBMolecule

        if isinstance(target, AbInitioTargetSchema) and target.fit_force is True:
            raise NotImplementedError()

        assert len(qc_records) == 1
        qc_record, off_molecule = qc_records[0]

        qc_record_id = (
            qc_record.extras["id"] if "id" in qc_record.extras else qc_record.id
        )

        # form a Molecule object from the first torsion grid data
        if isinstance(qc_record, TorsionDriveRecord):
            grid_energies = qc_record.get_final_energies()
        elif isinstance(qc_record, TorsionDriveResult):
            grid_energies = {
                tuple(json.loads(_standardize_grid_id_str(key))): value
                for key, value in qc_record.final_energies.items()
            }
        else:
            raise NotImplementedError()

        grid_conformers = {
            tuple(json.loads(grid_id)): conformer.value_in_unit(unit.angstrom)
            for grid_id, conformer in zip(
                off_molecule.properties["grid_ids"], off_molecule.conformers
            )
        }

        grid_ids = sorted(grid_energies, key=lambda x: x[0])

        # Create a FB molecule object from the QCData molecule.
        fb_molecule = FBMolecule()
        fb_molecule.Data = {
            "resname": ["UNK"] * off_molecule.n_atoms,
            "resid": [0] * off_molecule.n_atoms,
            "elem": [atom.element.symbol for atom in off_molecule.atoms],
            "bonds": [
                (bond.atom1_index, bond.atom2_index) for bond in off_molecule.bonds
            ],
            "name": f"{qc_record_id}",
            "xyzs": [grid_conformers[grid_id] for grid_id in grid_ids],
            "qm_energies": [grid_energies[grid_id] for grid_id in grid_ids],
            "comms": [f"torsion grid {grid_id}" for grid_id in grid_ids],
        }

        # Write the data
        fb_molecule.write("qdata.txt")
        fb_molecule.write("scan.xyz")

        off_molecule = copy.deepcopy(off_molecule)
        off_molecule._conformers = [off_molecule.conformers[0]]
        off_molecule.to_file("input.sdf", "SDF")

        # OpenFF does not map molecules into PDB well (it leads to files where Br is
        # confused with B for example), so we use ForceBalance instead.
        fb_molecule.Data["xyzs"] = [fb_molecule.Data["xyzs"][0]]
        del fb_molecule.Data["qm_energies"]
        del fb_molecule.Data["comms"]
        fb_molecule.write("conf.pdb")

        metadata = qc_record.keywords.dict()

        metadata["torsion_grid_ids"] = [
            grid_id if not isinstance(grid_id, str) else tuple(json.loads(grid_id))
            for grid_id in grid_ids
        ]

        metadata["energy_decrease_thresh"] = None
        metadata["energy_upper_limit"] = target.energy_cutoff

        with open("metadata.json", "w") as file:
            file.write(json.dumps(metadata))


class TorsionProfileTargetFactory(
    AbInitioTargetFactory, _TargetFactory[TorsionProfileTargetSchema]
):
    @classmethod
    def _target_name_prefix(cls) -> str:
        return "torsion"

    @classmethod
    def _generate_target(
        cls,
        target: TorsionProfileTargetSchema,
        qc_records: List[
            Tuple[Union[TorsionDriveRecord, TorsionDriveResult], Molecule]
        ],
    ):
        # noinspection PyTypeChecker
        super(TorsionProfileTargetFactory, cls)._generate_target(target, qc_records)

        qc_record, off_molecule = qc_records[0]

        if isinstance(qc_record, TorsionDriveRecord):
            grid_energies = qc_record.get_final_energies()
        elif isinstance(qc_record, TorsionDriveResult):
            grid_energies = {
                tuple(json.loads(_standardize_grid_id_str(key))): value
                for key, value in qc_record.final_energies.items()
            }
        else:
            raise NotImplementedError()

        grid_ids = sorted(grid_energies, key=lambda x: x[0])

        metadata = qc_record.keywords.dict()
        metadata["torsion_grid_ids"] = [
            grid_id if not isinstance(grid_id, str) else tuple(json.loads(grid_id))
            for grid_id in grid_ids
        ]

        metadata["energy_decrease_thresh"] = None
        metadata["energy_upper_limit"] = target.energy_cutoff

        with open("metadata.json", "w") as file:
            file.write(json.dumps(metadata))


class VibrationTargetFactory(_TargetFactory[VibrationTargetSchema]):
    @classmethod
    def _target_name_prefix(cls) -> str:
        return "vib-freq"

    @classmethod
    def _compute_normal_modes(
        cls, mass_weighted_hessian: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Computes the normal modes from a mass weighted hessian.

        Notes:
            This function was taken from the ``make_vib_freq_target.py`` script in the
            ``openforcefield-forcebalance`` repository at commit hash f689096.

        Args:
            mass_weighted_hessian: The mass weighted hessian to compute the normal
                modes from.

        Returns:
            A tuple of the frequencies and the corresponding normal modes.
        """

        # 1. diagonalize the hessian matrix
        eigen_values, eigen_vectors = np.linalg.eigh(mass_weighted_hessian)

        # 2. convert eigenvalues to frequencies

        # TODO: Magic numbers need to be replaced with simtk based conversion factors.
        coefficient = 0.5 / np.pi * 33.3564095  # 10^12 Hz => cm-1

        negatives = (eigen_values >= 0).astype(int) * 2 - 1  # record the negative ones
        frequencies = np.sqrt(np.abs(eigen_values)) * coefficient * negatives

        # 3. convert eigenvectors to normal modes
        noa = int(len(mass_weighted_hessian) / 3)

        normal_modes = eigen_vectors
        normal_modes = normal_modes.T.reshape(noa * 3, noa, 3)

        # step 5: remove the 6 freqs with smallest abs value and corresponding normal
        # modes
        n_remove = 5 if noa == 2 else 6

        larger_freq_idxs = np.sort(
            np.argpartition(np.abs(frequencies), n_remove)[n_remove:]
        )

        frequencies = frequencies[larger_freq_idxs]
        normal_modes = normal_modes[larger_freq_idxs]

        return frequencies, normal_modes

    @classmethod
    def _create_vdata_file(
        cls,
        qc_record: Union[ResultRecord, "AtomicResult"],
        qc_molecule: "QCMolecule",
        off_molecule: OFFMolecule,
    ):
        """Creates a file containing the vibrational frequency data.

        Notes:
            This function was taken from the ``make_vib_freq_target.py`` script in the
            ``openforcefield-forcebalance`` repository at commit hash f689096.

        Args:
            qc_record: The QC record containing the target hessian data.
            qc_molecule: The QC molecule associated with the QC record.
            off_molecule: An OpenFF representation of the QC molecule.
        """

        qc_record_id = (
            qc_record.extras["id"] if "id" in qc_record.extras else qc_record.id
        )

        if qc_record.driver.value != "hessian" or qc_record.return_result is None:

            raise QCRecordMissMatchError(
                f"The QC record with id={qc_record_id} does not contain the gradient "
                f"information required by a vibration fitting target."
            )

        # Check the magnitude of the gradient
        gradient = qc_record.extras["qcvars"]["CURRENT GRADIENT"]

        if np.abs(gradient).max() > 1e-3:

            logger.warning(
                f"the max gradient of record={qc_record_id} is greater than 1e-3"
            )

        # Get the list of masses for the molecule to be consistent with ForceBalance
        masses = np.array(
            [atom.mass.value_in_unit(unit.dalton) for atom in off_molecule.atoms]
        )

        # Compute the mass-weighted hessian
        invert_sqrt_mass_array_repeat = 1.0 / np.sqrt(masses.repeat(3))

        hessian = qc_record.return_result.reshape((len(masses) * 3, len(masses) * 3))

        mass_weighted_hessian = (
            hessian
            * invert_sqrt_mass_array_repeat[:, np.newaxis]
            * invert_sqrt_mass_array_repeat[np.newaxis, :]
        )

        # Convert units from Eh / bohr^2 * dalton to 10^24 s^-2
        # TODO: Magic numbers need to be replaced with simtk based conversion factors.
        mass_weighted_hessian *= 937583.07

        # Perform the normal mode analysis
        frequencies, normal_modes = cls._compute_normal_modes(mass_weighted_hessian)

        # write vdata.txt
        with open("vdata.txt", "w") as file:

            file.write(qc_molecule.to_string("xyz") + "\n")

            for frequency, normal_mode in zip(frequencies, normal_modes):

                file.write(f"{frequency}\n")

                for nx, ny, nz in normal_mode:
                    file.write(f"{nx:13.4f} {ny:13.4f} {nz:13.4f}\n")

                file.write("\n")

    @classmethod
    def _generate_target(
        cls,
        target: VibrationTargetSchema,
        qc_records: List[Tuple[Union[ResultRecord, "AtomicResult"], Molecule]],
    ):

        from forcebalance.molecule import Molecule as FBMolecule

        assert len(qc_records) == 1
        qc_record, off_molecule = qc_records[0]
        qc_record_id = (
            qc_record.extras["id"] if "id" in qc_record.extras else qc_record.id
        )

        fb_molecule = FBMolecule()
        fb_molecule.Data = {
            "resname": ["UNK"] * off_molecule.n_atoms,
            "resid": [0] * off_molecule.n_atoms,
            "elem": [atom.element.symbol for atom in off_molecule.atoms],
            "bonds": [
                (bond.atom1_index, bond.atom2_index) for bond in off_molecule.bonds
            ],
            "name": f"{qc_record_id}",
            "xyzs": [off_molecule.conformers[0].value_in_unit(unit.angstrom)],
        }

        # form a Molecule object from the first torsion grid data
        fb_molecule.write("conf.pdb")
        off_molecule.to_file("input.sdf", "SDF")

        cls._create_vdata_file(qc_record, off_molecule.to_qcschema(), off_molecule)


class OptGeoTargetFactory(_TargetFactory[OptGeoTargetSchema]):
    @classmethod
    def _target_name_prefix(cls) -> str:
        return "opt-geo"

    @classmethod
    def _section_extras_to_exclude(cls) -> List[str]:
        return ["batch_size"]

    @classmethod
    def _batch_qc_records(
        cls, target: OptGeoTargetSchema, qc_records: List[RecordBase]
    ):

        batch_size = int(target.extras.get("batch_size", 50))

        n_records = len(qc_records)
        n_targets = (n_records + batch_size - 1) // batch_size

        return {
            f"{cls._target_name_prefix()}-batch-{target_index}": qc_records[
                target_index * batch_size : (target_index + 1) * batch_size
            ]
            for target_index in range(n_targets)
        }

    @classmethod
    def _generate_target(
        cls,
        target: OptGeoTargetSchema,
        qc_records: List[
            Tuple[Union[OptimizationRecord, OptimizationResult], Molecule]
        ],
    ):

        from forcebalance.molecule import Molecule as FBMolecule

        record_names = []

        for i, (qc_record, off_molecule) in enumerate(qc_records):

            qc_record_id = (
                qc_record.extras["id"] if "id" in qc_record.extras else qc_record.id
            )

            record_name = f"{qc_record_id}-{i}"
            record_names.append(record_name)

            # form a Molecule object from the first torsion grid data
            qc_molecule = off_molecule.to_qcschema()

            with open(f"{record_name}.xyz", "w") as file:
                file.write(qc_molecule.to_string("xyz"))

            fb_molecule = FBMolecule()
            fb_molecule.Data = {
                "resname": ["UNK"] * off_molecule.n_atoms,
                "resid": [0] * off_molecule.n_atoms,
                "elem": [atom.element.symbol for atom in off_molecule.atoms],
                "bonds": [
                    (bond.atom1_index, bond.atom2_index) for bond in off_molecule.bonds
                ],
                "name": f"{qc_record_id}",
                "xyzs": [off_molecule.conformers[0].value_in_unit(unit.angstrom)],
            }

            fb_molecule.write(f"{record_name}.pdb")
            off_molecule.to_file(f"{record_name}.sdf", "SDF")

        # Create the options file
        with open("optgeo_options.txt", "w") as file:
            file.write(OptGeoOptionsTemplate.generate(target, record_names))


class ForceBalanceInputFactory:
    """This is the main factory which will generate all of the required inputs for a
    ForceBalance optimization."""

    @classmethod
    def _generate_force_field_directory(
        cls, optimization_schema: BaseOptimizationSchema
    ):

        os.makedirs("forcefield", exist_ok=True)

        force_field = optimization_schema.get_fitting_force_field()
        force_field.to_file(os.path.join("forcefield", "force-field.offxml"))

    @classmethod
    def generate(
        cls,
        root_directory: Union[str, Path],
        optimization_schema: BaseOptimizationSchema,
    ):

        if not isinstance(optimization_schema.optimizer, ForceBalanceSchema):

            raise OptimizerError(
                "Inputs can only be generated using this factory for optimizations "
                "which use ForceBalance as the optimizer."
            )

        target_factories = {
            AbInitioTargetSchema: AbInitioTargetFactory,
            TorsionProfileTargetSchema: TorsionProfileTargetFactory,
            VibrationTargetSchema: VibrationTargetFactory,
            OptGeoTargetSchema: OptGeoTargetFactory,
        }

        if not isinstance(optimization_schema.optimizer, ForceBalanceSchema):

            raise OptimizerError(
                "The `ForceBalanceInputFactory` can only create inputs from an "
                "optimization schema which uses a force balance optimizer."
            )

        # Create the root directory.
        os.makedirs(root_directory, exist_ok=True)

        # Temporarily switch to the root directory to make setting up the folder
        # structure easier.
        with temporary_cd(str(root_directory)):

            target_sections = []

            # Create the target directories
            os.makedirs("targets", exist_ok=True)

            with (temporary_cd("targets")):

                for target in optimization_schema.targets:

                    target_factory = target_factories[target.__class__]
                    target_sections.append(target_factory.generate(".", target))

            targets_section = "\n\n".join(target_sections)

            # Create the optimize.in file
            priors = {
                name: value
                for name, value in [
                    target_parameter.get_prior()
                    for target_parameter in optimization_schema.parameter_settings
                ]
            }

            with open("optimize.in", "w") as file:

                file.write(
                    InputOptionsTemplate.generate(
                        optimization_schema.optimizer,
                        targets_section=targets_section,
                        priors=priors,
                    )
                )

            # Create the force field directory
            cls._generate_force_field_directory(optimization_schema)
