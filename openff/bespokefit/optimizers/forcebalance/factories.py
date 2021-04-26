import abc
import json
import logging
import os
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Callable,
    Collection,
    Dict,
    Generic,
    List,
    Tuple,
    TypeVar,
    Union,
)

import cmiles
import numpy as np
from openff.toolkit.topology import Molecule as OFFMolecule
from qcportal import FractalClient
from qcportal.models import TorsionDriveRecord
from qcportal.models.records import RecordBase, ResultRecord
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
from openff.bespokefit.schema.data import BespokeQCData
from openff.bespokefit.schema.fitting import BaseOptimizationSchema
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.targets import (
    AbInitioTargetSchema,
    ExistingQCData,
    OptGeoTargetSchema,
    TargetSchema,
    TorsionProfileTargetSchema,
    VibrationTargetSchema,
)
from openff.bespokefit.utilities import temporary_cd

if TYPE_CHECKING:
    from qcelemental.models import Molecule as QCMolecule

logger = logging.getLogger(__name__)

S = TypeVar("S", bound=RecordBase)
T = TypeVar("T", bound=TargetSchema)

_TARGET_SECTION_TEMPLATES = {
    AbInitioTargetSchema: AbInitioTargetTemplate,
    TorsionProfileTargetSchema: TorsionProfileTargetTemplate,
    OptGeoTargetSchema: OptGeoTargetTemplate,
    VibrationTargetSchema: VibrationTargetTemplate,
}


class _TargetFactory(Generic[T], abc.ABC):
    @classmethod
    @abc.abstractmethod
    def _target_name_prefix(cls) -> str:
        raise NotImplementedError()

    @classmethod
    def _generate_targets_section(cls, target_template: T, target_names: List[str]):
        """Creates the target sections which will need to be added to the main
        ForceBalance 'options.in' file."""

        template_factory = _TARGET_SECTION_TEMPLATES[target_template.__class__]
        return template_factory.generate(target_template, target_names)

    @classmethod
    def _paginated_query(
        cls,
        qc_client: FractalClient,
        query_function: Callable[..., S],
        record_ids: Collection[str],
    ) -> List[S]:

        results = {}

        query_limit = qc_client.server_info["query_limit"]

        paginating = True
        page_index = 0

        print(f"retrieving QC records (n={len(record_ids)})")

        with tqdm(total=len(record_ids)) as progress_bar:

            while paginating:

                page_results = query_function(
                    id=record_ids,
                    limit=query_limit,
                    skip=page_index,
                )

                results.update({result.id: result for result in page_results})

                paginating = len(page_results) > 0
                page_index += query_limit

                progress_bar.update(len(page_results))

        missing_records = {*record_ids} - {*results}

        if len(missing_records) > 0:

            raise QCRecordMissMatchError(
                f"The follow QC records could not be retrieved from the server at "
                f"{qc_client.address}: {missing_records}"
            )

        return [*results.values()]

    @classmethod
    @abc.abstractmethod
    def _retrieve_qc_records(
        cls, qc_client: FractalClient, record_ids: Collection[str]
    ) -> List[RecordBase]:
        """Retrieves a set of QC data record using the provided QC client.

        Args:
            qc_client: The QC client to retrieve the record using.
            record_ids: The ids of the record to retrieve.

        Returns:
            The retrieved records.
        """
        raise NotImplementedError()

    @classmethod
    def _qc_molecule_to_off(cls, qc_molecule: "QCMolecule") -> OFFMolecule:

        qc_molecule_schema = qc_molecule.dict(encoding="json")

        # Try to load the molecule from stored CMILES attributes.
        if "extras" in qc_molecule_schema and "attributes" not in qc_molecule_schema:
            qc_molecule_schema["attributes"] = qc_molecule_schema["extras"]

        if "attributes" in qc_molecule_schema:
            off_molecule = OFFMolecule.from_qcschema(qc_molecule_schema)

        # If that fails try loading the molecule using CMILES directly.
        else:
            off_molecule = OFFMolecule.from_rdkit(
                cmiles.utils.load_molecule(
                    {
                        "symbols": qc_molecule.symbols,
                        "connectivity": qc_molecule.connectivity,
                        "geometry": qc_molecule.geometry.flatten(),
                        "molecular_charge": qc_molecule.molecular_charge,
                        "molecular_multiplicity": qc_molecule.molecular_multiplicity,
                    },
                    toolkit="rdkit",
                )
            )

        return off_molecule

    @classmethod
    def _batch_qc_records(
        cls, target: TargetSchema, qc_records: List[RecordBase]
    ) -> Dict[str, List[RecordBase]]:
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

        return {
            f"{cls._target_name_prefix()}-{qc_record.id}": [qc_record]
            for qc_record in qc_records
        }

    @classmethod
    @abc.abstractmethod
    def _generate_target(cls, target: T, qc_records: List[RecordBase]):
        """Create the required input files for a particular target.

        Notes:
            * This function assumes that the files should be created in the current
              working directory.
        """
        raise NotImplementedError()

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
        if isinstance(target.reference_data, ExistingQCData):

            qc_client = FractalClient(target.reference_data.qcfractal_address)

            qc_records = cls._retrieve_qc_records(
                qc_client, target.reference_data.record_ids
            )

        elif isinstance(target.reference_data, BespokeQCData):
            raise NotImplementedError()

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
    def _retrieve_qc_records(
        cls, qc_client: FractalClient, record_ids: Collection[str]
    ) -> List[TorsionDriveRecord]:
        return cls._paginated_query(qc_client, qc_client.query_procedures, record_ids)

    @classmethod
    def _generate_target(cls, target: T, qc_records: List[TorsionDriveRecord]):

        from forcebalance.molecule import Molecule as FBMolecule
        from forcebalance.molecule import bohr2ang

        assert len(qc_records) == 1
        qc_record = qc_records[0]

        # form a Molecule object from the first torsion grid data
        grid_molecules = qc_record.get_final_molecules()
        grid_energies = qc_record.get_final_energies()

        grid_ids = sorted(grid_molecules, key=lambda x: x[0])

        # Create a FB molecule object from the QCData molecule.
        qc_molecule = grid_molecules[grid_ids[0]]
        off_molecule = cls._qc_molecule_to_off(qc_molecule)

        fb_molecule = FBMolecule()
        fb_molecule.Data = {
            "elem": qc_molecule.symbols,
            "bonds": [(bond[0], bond[1]) for bond in qc_molecule.connectivity],
            "name": qc_molecule.name,
            "xyzs": [
                grid_molecules[grid_id].geometry.reshape(-1, 3) * bohr2ang
                for grid_id in grid_ids
            ],
            "qm_energies": [grid_energies[grid_id] for grid_id in grid_ids],
            "comms": [
                f"{grid_molecules[grid_id].name} at torsion grid {grid_id}"
                for grid_id in grid_ids
            ],
        }

        # Write the data
        fb_molecule.write("qdata.txt")
        fb_molecule.write("scan.xyz")

        off_molecule.to_file("conf.pdb", "PDB")
        off_molecule.to_file("input.sdf", "SDF")

        metadata = qc_record.keywords.dict()
        metadata["torsion_grid_ids"] = grid_ids

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
        qc_records: List[TorsionDriveRecord],
    ):
        # noinspection PyTypeChecker
        super(TorsionProfileTargetFactory, cls)._generate_target(target, qc_records)

        qc_record = qc_records[0]

        grid_molecules = qc_record.get_final_molecules()
        grid_ids = sorted(grid_molecules, key=lambda x: x[0])

        metadata = qc_record.keywords.dict()
        metadata["torsion_grid_ids"] = grid_ids

        metadata["energy_decrease_thresh"] = None
        metadata["energy_upper_limit"] = target.energy_cutoff

        with open("metadata.json", "w") as file:
            file.write(json.dumps(metadata))


class VibrationTargetFactory(_TargetFactory[VibrationTargetSchema]):
    @classmethod
    def _target_name_prefix(cls) -> str:
        return "vib-freq"

    @classmethod
    def _retrieve_qc_records(
        cls, qc_client: FractalClient, record_ids: Collection[str]
    ) -> List[ResultRecord]:
        return cls._paginated_query(qc_client, qc_client.query_results, record_ids)

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
        qc_record: ResultRecord,
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

        if qc_record.driver.value != "hessian" or qc_record.return_result is None:

            raise QCRecordMissMatchError(
                f"The QC record with id={qc_record.id} does not contain the gradient "
                f"information required by a vibration fitting target."
            )

        # Check the magnitude of the gradient
        gradient = qc_record.extras["qcvars"]["CURRENT GRADIENT"]

        if np.abs(gradient).max() > 1e-3:

            logger.warning(
                f"the max gradient of record={qc_record.id} is greater than 1e-3"
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
        cls, target: VibrationTargetSchema, qc_records: List[ResultRecord]
    ):

        assert len(qc_records) == 1
        qc_record = qc_records[0]

        # form a Molecule object from the first torsion grid data
        qc_molecule = qc_record.get_molecule()
        off_molecule = cls._qc_molecule_to_off(qc_molecule)

        off_molecule.to_file("conf.pdb", "PDB")
        off_molecule.to_file("input.sdf", "SDF")

        cls._create_vdata_file(qc_record, qc_molecule, off_molecule)


class OptGeoTargetFactory(_TargetFactory[OptGeoTargetSchema]):
    @classmethod
    def _target_name_prefix(cls) -> str:
        return "opt-geo"

    @classmethod
    def _retrieve_qc_records(
        cls, qc_client: FractalClient, record_ids: Collection[str]
    ) -> List[ResultRecord]:
        return cls._paginated_query(qc_client, qc_client.query_results, record_ids)

    @classmethod
    def _batch_qc_records(
        cls, target: OptGeoTargetSchema, qc_records: List[RecordBase]
    ):

        # TODO: Uncomment when #16 is merged.
        # batch_size = target.extras.get("batch_size", 50)
        batch_size = 50

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
        cls, target: OptGeoTargetSchema, qc_records: List[ResultRecord]
    ):

        record_names = []

        for i, qc_record in enumerate(qc_records):

            record_name = f"{qc_record.id}-{i}"
            record_names.append(record_name)

            # form a Molecule object from the first torsion grid data
            qc_molecule = qc_record.get_molecule()

            with open(f"{record_name}.xyz", "w") as file:
                file.write(qc_molecule.to_string("xyz"))

            off_molecule = cls._qc_molecule_to_off(qc_molecule)

            off_molecule.to_file(f"{record_name}.pdb", "PDB")
            off_molecule.to_file(f"{record_name}.sdf", "SDF")

        # Create the options file
        with open("optget_options.txt", "w") as file:
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

        print("making forcebalance file system in ", root_directory)

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
