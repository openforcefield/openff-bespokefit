import abc
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from openff.qcsubmit.common_structures import MoleculeAttributes
from openff.qcsubmit.datasets import DatasetEntry, OptimizationEntry, TorsionDriveEntry
from openff.qcsubmit.factories import TorsiondriveDatasetFactory
from openff.toolkit.topology import Molecule
from pydantic import Field, validator
from qcelemental.models.types import Array
from qcportal.models import TorsionDriveRecord
from qcportal.models.records import OptimizationRecord, RecordBase, ResultRecord
from simtk import unit
from typing_extensions import Literal

from openff.bespokefit.exceptions import DihedralSelectionError, MoleculeMissMatchError
from openff.bespokefit.utilities.pydantic import SchemaBase


class BaseReferenceData(SchemaBase, abc.ABC):
    """The base for models which contain the reference data produced by a fitting task."""

    record: RecordBase = Field(
        ..., description="The QC record storing the outputs of the task."
    )
    cmiles: str = Field(
        ...,
        description="The CMILES description of the molecule associated with the task.",
    )

    @property
    def molecule(self) -> Molecule:
        """The OpenFF molecule associated with this record."""

        return Molecule.from_mapped_smiles(self.cmiles, allow_undefined_stereo=True)


class BaseFittingTask(SchemaBase, abc.ABC):
    """The base class for a fitting task.

    Fitting tasks will typically involve generating a bespoke QC data set for a
    specified set of molecules / fragments.
    """

    # used to distinguish between fitting entry types
    task_type: Literal["FittingTask"] = "FittingTask"

    name: str = Field(
        ...,
        description="The name of the fitting entry, this is normally the molecule name "
        "and task which generates the input data like torsiondrive.",
    )

    attributes: MoleculeAttributes = Field(
        ...,
        description="A dictionary containing the cmiles information about the molecule.",
    )
    input_conformers: List[Array[np.ndarray]] = Field(
        ...,
        description="The list of conformers stored as a np.ndarray so we can serialize "
        "to json.",
    )

    extras: Dict[str, Any] = Field(
        dict(),
        description="Any extra information that might be needed by the target.",
    )
    provenance: Dict[str, Any] = Field(
        dict(),
        description="A dictionary of the provenance info used to create this fitting "
        "entry.",
    )

    fragment: bool = Field(
        ..., description="If the molecule is a fragment of a parent."
    )
    fragment_parent_mapping: Optional[Dict[int, int]] = Field(
        None,
        description="If the molecule is a fragment store the fragment to parent "
        "mapping here, to use this enter the index of the atom in the fragment to get "
        "the corresponding index of the parent atom.",
    )

    reference_data: Optional[BaseReferenceData] = Field(
        None, description="The results of executing the task."
    )

    error_message: Optional[str] = Field(
        None,
        description="Any errors recorded while generating the fitting data should be "
        "listed here.",
    )

    def __init__(self, molecule: Optional[Molecule] = None, **kwargs):
        """
        Handle the unpacking of the input conformers.
        """
        input_confs = kwargs.get("input_conformers", [])
        if not input_confs and molecule is not None:
            # get from the molecule
            for conformer in molecule.conformers:
                input_confs.append(conformer.in_units_of(unit.angstrom))
            kwargs["input_conformers"] = input_confs

        super(BaseFittingTask, self).__init__(**kwargs)

    @validator("input_conformers")
    def _check_conformers(
        cls, conformers: List[Array[np.array]]
    ) -> List[Array[np.array]]:
        """
        Take the list of input conformers which will be flat and reshape them.
        """
        reshaped_conformers = []
        for conformer in conformers:
            if conformer.shape[-1] != 3:
                reshaped_conformers.append(conformer.reshape((-1, 3)))
            else:
                reshaped_conformers.append(conformer)
        return reshaped_conformers

    @property
    def has_errors(self) -> bool:
        """Return if collecting the reference data resulted in an error."""
        return True if self.error_message is not None else False

    @property
    def graph_molecule(self) -> Molecule:
        """
        Create just the OpenFF graph molecule representation for the FittingSchema no
        geometry is included.

        Note:
            This is useful for quick comparsions as the geometry does not have to be
            built and validated.
        """

        return Molecule.from_mapped_smiles(
            self.attributes.canonical_isomeric_explicit_hydrogen_mapped_smiles
        )

    @property
    def initial_molecule(self) -> Molecule:
        """
        Create an openFF molecule representation for the FittingSchema with the input
        geometries.
        """
        off_mol = self.graph_molecule
        # check if there are any complete workflow stages
        for conformer in self.input_conformers:
            geometry = unit.Quantity(value=conformer, unit=unit.angstrom)
            off_mol.add_conformer(geometry)

        return off_mol

    def _get_general_hash_data(self) -> str:
        """
        Collect the general hash data.
        """
        inchi = self.graph_molecule.to_inchikey(fixed_hydrogens=True)
        return inchi

    @abc.abstractmethod
    def _get_task_hash(self) -> str:
        """
        Get a specific task data that will be combined with general molecule data to
        make the hash.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_qcsubmit_task(self):
        """
        Generate a qcsubmit task for this fitting entry.
        """
        raise NotImplementedError()

    def get_task_hash(self) -> str:
        """
        Get a hash of the current task.
        """
        m = hashlib.sha1()
        hash_string = self._get_general_hash_data() + self._get_task_hash()
        m.update(hash_string.encode("utf-8"))
        return m.hexdigest()

    @abc.abstractmethod
    def update_with_results(self, record: RecordBase, molecule: Molecule) -> None:
        """
        Take a results class and update the results in the schema.
        """
        raise NotImplementedError()

    @property
    def collected(self) -> bool:
        return self.reference_data is not None

    def __eq__(self, other: "BaseFittingTask") -> bool:
        """
        Check if the job hash is the same.
        """
        return self.get_task_hash() == other.get_task_hash()


class TorsionTaskReferenceData(BaseReferenceData):
    """A model which stores the outputs of executing a ``TorsionTask``."""

    record: TorsionDriveRecord = Field(
        ..., description="The QC record storing the output of the torsion drive."
    )

    conformers: Dict[str, Array[float]] = Field(
        ...,
        description="The minimum energy conformer [bohr] associated with each grid id "
        "stored as a flat array with shape (3 * n_atoms). The ordering of the conformer "
        "must match the ordering specified by the ``cmiles`` field.",
    )

    @property
    def molecule(self) -> Molecule:
        """The OpenFF molecule associated with this record which contains the minimum
        energy conformer at each grid id. The grid ids themselves will be stored in
        ``molecule.properties["grid_ids"]``, such that ``molecule.conformers[i]``
        corresponds to the minimum energy structure at grid id
        ``molecule.properties["grid_ids"][i]``.
        """

        molecule = Molecule.from_mapped_smiles(self.cmiles, allow_undefined_stereo=True)

        molecule.properties["grid_ids"] = []

        for grid_id, conformer_array in self.conformers.items():
            molecule.add_conformer(
                conformer_array.reshape((molecule.n_atoms, 3)) * unit.bohr
            )

            molecule.properties["grid_ids"].append(grid_id)

        return molecule


class TorsionTask(BaseFittingTask):
    """A schema detailing a torsion drive fitting target."""

    task_type: Literal["torsion1d"] = "torsion1d"

    dihedrals: Optional[List[Tuple[int, int, int, int]]] = Field(
        None,
        description="The dihedrals which are to be driven during the collection "
        "workflow.",
    )

    reference_data: Optional[TorsionTaskReferenceData] = Field(
        None, description="The results of the torsion drive."
    )

    @validator("dihedrals")
    def _validate_dihedrals(
        cls, dihedrals: Optional[List[Tuple[int, int, int, int]]]
    ) -> Optional[List[Tuple[int, int, int, int]]]:
        """Dihedrals targeted for driving and optimization are stored here make sure that
        only 1D or 2D scans are available.
        """

        if dihedrals is not None:
            # make sure we have a list of lists/tuples
            if len(dihedrals) == 4:
                # single list
                dihedrals = [
                    tuple(dihedrals),
                ]

            if len(dihedrals) >= 3:
                # make sure we are not doing more than 2D
                raise DihedralSelectionError(
                    f"A maximum of a 2D dihedral scan is supported but a scan of length "
                    f"{len(dihedrals)} was given."
                )
        return dihedrals

    @property
    def central_bonds(self) -> List[Tuple[int, int]]:
        """
        Return a list of central bond tuples for the target torsions.
        """
        if self.dihedrals is not None:
            bonds = [(dihedral[1], dihedral[2]) for dihedral in self.dihedrals]
            return bonds

    def update_with_results(
        self, result_record: TorsionDriveRecord, result_molecule: Molecule
    ):
        """
        Take a torsiondrive result check if the molecule is the same and the same
        dihedral is targeted and apply the results.
        """

        if not isinstance(result_record, TorsionDriveRecord):
            raise TypeError("This task can only be updated with torsion drive records")

        # work out any mapping differences and update the result
        isomorphic, atom_map = Molecule.are_isomorphic(
            result_molecule, self.initial_molecule, return_atom_map=True
        )

        if not isomorphic:

            raise MoleculeMissMatchError(
                "Molecules are not isomorphic and the results can not be transferred."
            )

        # work out if the result and schema target the same dihedral via central bond
        # noinspection PyTypeChecker
        target_dihedral: Tuple[int, int, int, int] = tuple(
            atom_map[i] for i in result_record.keywords.dihedrals[0]
        )

        if {*self.dihedrals[0][1:3]} != {*target_dihedral[1:3]}:

            raise DihedralSelectionError(
                "Molecules are the same but do not target the same dihedral."
            )

        # we need to change the target dihedral to match what the result is
        # for
        self.dihedrals = [target_dihedral]

        # get the optimization results in order of the angle - we need this data later
        self.reference_data = TorsionTaskReferenceData(
            record=result_record,
            cmiles=result_molecule.to_smiles(True, True, True),
            conformers={
                grid_id: conformer.value_in_unit(unit.bohr)
                for grid_id, conformer in zip(
                    result_molecule.properties["grid_ids"], result_molecule.conformers
                )
            },
        )

    def _get_task_hash(self) -> str:
        """
        Make the specific task has for this molecule.
        """
        dihedral = str(self.dihedrals)
        return "torsiondrive1d" + dihedral

    def get_qcsubmit_task(self) -> TorsionDriveEntry:
        """
        Build a qcsubmit torsiondrive entry for this molecule.
        """
        if not self.collected:

            # Note we only support 1D scans
            atom_map = dict((atom, i) for i, atom in enumerate(self.dihedrals[0]))
            molecule = self.initial_molecule
            molecule.properties["atom_map"] = atom_map

            factory = TorsiondriveDatasetFactory()
            index = factory.create_index(molecule)

            task = self.get_task_hash()
            attributes = self.attributes
            attributes.task_hash = task  # add in the task hash
            new_entry = TorsionDriveEntry(
                index=index,
                off_molecule=molecule,
                attributes=attributes,
                dihedrals=self.dihedrals,
                extras=self.extras,
            )
            return new_entry


class OptimizationTaskReferenceData(BaseReferenceData):
    """A model which stores the outputs of executing a ``OptimizationTask``."""

    record: OptimizationRecord = Field(
        ..., description="The QC record storing the output of the optimization."
    )

    conformer: Array[float] = Field(
        ...,
        description="The final minimum energy conformer [bohr] stored as a flat array "
        "with shape (3 * n_atoms). The ordering of the conformer must match the "
        "ordering specified by the ``cmiles`` field.",
    )

    @property
    def molecule(self) -> Molecule:
        """The OpenFF molecule associated with this record which contains the final
        minimum energy conformer.
        """

        molecule = Molecule.from_mapped_smiles(self.cmiles, allow_undefined_stereo=True)

        molecule.add_conformer(
            self.conformer.reshape((molecule.n_atoms, 3)) * unit.bohr
        )

        return molecule


class OptimizationTask(BaseFittingTask):
    """
    A schema detailing an optimisation fitting target.
    """

    task_type: Literal["optimization"] = "optimization"

    reference_data: Optional[OptimizationTaskReferenceData] = Field(
        None, description="The results of the optimization."
    )

    def _get_task_hash(self) -> str:
        return "optimization"

    def get_qcsubmit_task(self) -> OptimizationEntry:
        """
        Generate an optimization entry for the molecule.
        """
        if not self.collected:
            return self._make_optimization_entry()

    def _make_optimization_entry(self) -> OptimizationEntry:
        """
        Make a qcsubmit optimization entry.
        """
        molecule = self.initial_molecule
        attributes = self.attributes
        attributes.task_hash = self.get_task_hash()
        index = molecule.to_smiles(
            isomeric=True,
            mapped=False,
            explicit_hydrogens=False,
        )
        opt_entry = OptimizationEntry(
            index=index,
            off_molecule=molecule,
            attributes=attributes,
            extras=self.extras,
            keywords={},
        )
        return opt_entry

    def update_with_results(
        self, result_record: OptimizationRecord, result_molecule: Molecule
    ):
        """
        Update the results of this task with an optimization result
        """

        if not isinstance(result_record, OptimizationRecord):
            raise TypeError("This task can only be updated with optimization records")

        # work out any mapping differences and update the result
        isomorphic, atom_map = Molecule.are_isomorphic(
            result_molecule, self.initial_molecule, return_atom_map=True
        )

        if not isomorphic:

            raise MoleculeMissMatchError(
                "Molecules are not isomorphic and the results can not be transferred."
            )

        if result_molecule.n_conformers != 1:

            raise MoleculeMissMatchError(
                "The molecule must contain the final minimum energy conformer."
            )

        # get the optimization results in order of the angle - we need this data later
        self.reference_data = OptimizationTaskReferenceData(
            record=result_record,
            cmiles=result_molecule.to_smiles(True, True, True),
            conformer=result_molecule.conformers[0].value_in_unit(unit.bohr),
        )


class HessianTaskReferenceData(BaseReferenceData):
    """A model which stores the outputs of executing a ``OptimizationTask``."""

    record: ResultRecord = Field(
        ..., description="The QC record storing the output of the task."
    )


class HessianTask(OptimizationTask):
    """
    A schema detailing a hessian generation task.
    """

    task_type: Literal["hessian"] = "hessian"

    optimization_data: Optional[OptimizationTaskReferenceData] = Field(
        None, description="The data generated by the optimization precursor task."
    )

    reference_data: Optional[HessianTaskReferenceData] = Field(
        None, description="The results of the optimization."
    )

    def _get_task_hash(self) -> str:
        """
        Get a task hash based on the current job that needs to be completed.
        """
        if self.optimization_data is None:
            return "optimization"
        else:
            return "hessian"

    def get_qcsubmit_task(self) -> Union[OptimizationEntry, DatasetEntry]:
        """
        Generate either an optimization task or a hessian single point task based on the
        progress of the workflow.
        """
        if not self.collected:
            if self.optimization_data is None:
                return self._make_optimization_entry()
            else:
                return self._make_hessian_entry()

    def _make_hessian_entry(self) -> DatasetEntry:
        """
        Make a single point entry to compute the hessian from the optimised geometry.
        """

        molecule = self.optimization_data.molecule

        _, atom_map = Molecule.are_isomorphic(
            molecule, self.graph_molecule, return_atom_map=True
        )

        # Make sure the optimization molecule has the same ordering as this record.
        molecule.remap(atom_map)

        task = self.get_task_hash()
        attributes = self.attributes
        attributes.task_hash = task
        index = molecule.to_smiles(
            isomeric=True,
            mapped=False,
            explicit_hydrogens=False,
        )
        new_entry = DatasetEntry(
            index=index,
            off_molecule=molecule,
            attributes=attributes,
            extras=self.extras,
        )
        return new_entry

    def update_with_results(
        self,
        result_record: Union[ResultRecord, OptimizationRecord],
        result_molecule: Molecule,
    ):
        raise NotImplementedError()


FittingTask = Union[TorsionTask, OptimizationTask, HessianTask]
