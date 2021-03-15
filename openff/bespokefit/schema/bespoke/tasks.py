import abc
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from openff.qcsubmit.common_structures import MoleculeAttributes
from openff.qcsubmit.datasets import DatasetEntry, OptimizationEntry, TorsionDriveEntry
from openff.qcsubmit.factories import TorsiondriveDatasetFactory
from openff.qcsubmit.results import (
    BasicResult,
    OptimizationEntryResult,
    SingleResult,
    TorsionDriveResult,
)
from openforcefield import topology as off
from pydantic import Field, validator
from qcelemental.models.types import Array
from simtk import unit
from typing_extensions import Literal

from openff.bespokefit.exceptions import DihedralSelectionError, MoleculeMissMatchError
from openff.bespokefit.utilities.pydantic import SchemaBase


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

    error_message: Optional[str] = Field(
        None,
        description="Any errors recorded while generating the fitting data should be "
        "listed here.",
    )

    def __init__(self, molecule: Optional[off.Molecule] = None, **kwargs):
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
    def graph_molecule(self) -> off.Molecule:
        """
        Create just the OpenFF graph molecule representation for the FittingSchema no
        geometry is included.

        Note:
            This is useful for quick comparsions as the geometry does not have to be
            built and validated.
        """

        return off.Molecule.from_mapped_smiles(
            self.attributes.canonical_isomeric_explicit_hydrogen_mapped_smiles
        )

    @property
    def initial_molecule(self) -> off.Molecule:
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
    def update_with_results(self, result) -> None:
        """
        Take a results class and update the results in the schema.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def reference_data(self) -> List[SingleResult]:
        """
        Return the reference data ready for fitting.
        """
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def collected(self) -> bool:
        """
        Return if the schema is complete and has reference data.
        """
        raise NotImplementedError()

    def _remap_single_result(
        self,
        mapping: Dict[int, int],
        new_molecule: off.Molecule,
        result: SingleResult,
        extras: Optional[Dict[str, Any]] = None,
    ) -> SingleResult:
        """
        Given a single result and a mapping remap the result ordering to match the
        fitting schema order.

        Parameters:
            mapping: The mapping between the old and new molecule.
            new_molecule: The new molecule in the correct order.
            result: The single result which should be remapped.
            extras: Any extras that should be added to the result.
        """
        new_molecule._conformers = []
        # re map the geometry and attach
        new_conformer = np.zeros((new_molecule.n_atoms, 3))
        for i in range(new_molecule.n_atoms):
            new_conformer[mapping[i]] = result.molecule.geometry[i]
        geometry = unit.Quantity(new_conformer, unit.bohr)
        new_molecule.add_conformer(geometry)
        # drop the bond order indices and just remap the gradient and hessian
        new_gradient = np.zeros((new_molecule.n_atoms, 3))
        for i in range(new_molecule.n_atoms):
            new_gradient[i] = result.gradient[mapping[i]]

        # #remap the hessian
        # new_hessian = np.zeros((3 * new_molecule.n_atoms, 3 * new_molecule.n_atoms))
        # # we need to move 3 entries at a time to keep them together
        # for i in range(new_molecule.n_atoms):
        #     new_hessian[i * 3: (i * 3) + 3] = result.hessian[mapping[i * 3]: mapping[(i * 3) + 3]]
        return SingleResult(
            molecule=new_molecule.to_qcschema(),
            id=result.id,
            energy=result.energy,
            gradient=new_gradient,
            hessian=None,
            extras=extras,
        )

    def __eq__(self, other: "BaseFittingTask") -> bool:
        """
        Check if the job hash is the same.
        """
        return self.get_task_hash() == other.get_task_hash()


class TorsionTask(BaseFittingTask):
    """A schema detailing a torsion drive fitting target."""

    task_type: Literal["torsion1d"] = "torsion1d"

    dihedrals: Optional[List[Tuple[int, int, int, int]]] = Field(
        None,
        description="The dihedrals which are to be driven during the collection "
        "workflow.",
    )

    torsiondrive_data: Optional[List[SingleResult]] = Field(
        None, description="The results of the torsiondrive."
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

    def update_with_results(self, results: TorsionDriveResult) -> None:
        """
        Take a torsiondrive result check if the molecule is the same and the same
        dihedral is targeted and apply the results.
        """
        # keep track of if we need to remap
        remap = False

        new_results = []
        if isinstance(results, TorsionDriveResult):
            # this is valid so work out any mapping differences and update the result
            isomorphic, atom_map = off.Molecule.are_isomorphic(
                results.molecule, self.initial_molecule, return_atom_map=True
            )
            if isomorphic:
                # if the atom map is not the same remap the result
                if atom_map != dict(
                    (i, i) for i in range(self.initial_molecule.n_atoms)
                ):
                    remap = True
                # work out if the result and schema target the same dihedral via central
                # bond
                dihedral = set(self.dihedrals[0][1:3])
                # now map the result dihedral back
                target_dihedral = [atom_map[i] for i in results.dihedrals[0]]
                if not dihedral.difference(set(target_dihedral[1:3])):
                    # we need to change the target dihedral to match what the result is
                    # for
                    self.dihedrals = [target_dihedral]
                    # get the optimization results in order of the angle
                    # we need this data later
                    for (
                        angle,
                        optimization_result,
                    ) in results.get_ordered_results():
                        if remap:
                            new_single_result = self._remap_single_result(
                                mapping=atom_map,
                                new_molecule=self.initial_molecule,
                                result=optimization_result,
                                extras={"dihedral_angle": angle},
                            )
                        else:
                            # get a new single result with the angle in it
                            result_dict = optimization_result.dict(
                                exclude={"wbo", "mbo"}
                            )
                            result_dict["extras"] = {"dihedral_angle": angle}
                            new_single_result = SingleResult(**result_dict)

                        new_results.append(new_single_result)
                    # set results back
                    self.torsiondrive_data = new_results

                else:
                    raise DihedralSelectionError(
                        "Molecules are the same but do not target the same dihedral."
                    )
            else:
                raise MoleculeMissMatchError(
                    "Molecules are not isomorphic and the results can not be "
                    "transferred."
                )

    @property
    def collected(self) -> bool:
        """
        Do we want some more explicit checking here?
        """
        return True if self.torsiondrive_data is not None else False

    def reference_data(self) -> List[SingleResult]:
        """
        Return the reference data ready for fitting.
        """
        return self.torsiondrive_data

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


class OptimizationTask(BaseFittingTask):
    """
    A schema detailing an optimisation fitting target.
    """

    task_type: Literal["optimization"] = "optimization"
    optimization_data: Optional[SingleResult] = Field(
        None,
        description="The results of the optimization which contains the optimised "
        "geometry",
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

    def update_with_results(self, result: OptimizationEntryResult) -> None:
        """
        Update the results of this task with an optimization result
        """
        raise NotImplementedError()

    def reference_data(self) -> SingleResult:
        return self.optimization_data

    @property
    def collected(self) -> bool:
        return True if self.optimization_data is not None else False


class HessianTask(OptimizationTask):
    """
    A schema detailing a hessian generation task.
    """

    task_type: Literal["hessian"] = "hessian"
    hessian_data: Optional[SingleResult] = Field(
        None, description="The results of a hessian calculation."
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
        from simtk import unit

        molecule = self.graph_molecule
        geometry = unit.Quantity(self.optimization_data.molecule.geometry, unit.bohr)
        molecule.add_conformer(coordinates=geometry)
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

    def update_with_results(self, result: BasicResult) -> None:
        raise NotImplementedError()

    def reference_data(self) -> SingleResult:
        return self.hessian_data

    @property
    def collected(self) -> bool:
        return True if self.hessian_data is not None else False


FittingTask = Union[TorsionTask, OptimizationTask, HessianTask]
