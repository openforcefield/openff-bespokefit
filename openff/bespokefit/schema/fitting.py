import abc
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union

import numpy as np
from openforcefield import topology as off
from openforcefield.typing.engines.smirnoff import ForceField
from pydantic import Field, Protocol, validator
from qcelemental.models.types import Array
from simtk import unit
from typing_extensions import Literal

from openff.bespokefit.common_structures import SchemaBase, SmirksSettings, Status
from openff.bespokefit.exceptions import (
    DihedralSelectionError,
    MoleculeMissMatchError,
    OptimizerError,
    TaskMissMatchError,
)
from openff.bespokefit.schema.smirks import (
    AngleSmirks,
    AtomSmirks,
    BondSmirks,
    SmirksType,
    TorsionSmirks,
    ValidatedSmirks,
    smirks_from_dict,
)
from openff.qcsubmit.common_structures import MoleculeAttributes, QCSpec
from openff.qcsubmit.datasets import (
    BasicDataset,
    DatasetEntry,
    OptimizationDataset,
    OptimizationEntry,
    TorsiondriveDataset,
    TorsionDriveEntry,
)
from openff.qcsubmit.results import (
    BasicCollectionResult,
    BasicResult,
    OptimizationCollectionResult,
    OptimizationEntryResult,
    SingleResult,
    TorsionDriveCollectionResult,
    TorsionDriveResult,
)
from openff.qcsubmit.serializers import deserialize, serialize


class FittingTask(SchemaBase, abc.ABC):
    """
    This is the fitting schema which has instructions on how to collect the reference data and fit the parameters for a molecule.
    """

    # used to distinguish between fitting entry types
    task_type: Literal["FittingTask"] = "FittingTask"

    name: str = Field(
        ...,
        description="The name of the fitting entry, this is normally the molecule name and task which generates the input data like torsiondrive.",
    )
    attributes: MoleculeAttributes = Field(
        ...,
        description="A dictionary containing the cmiles information about the molecule.",
    )
    provenance: Dict[str, Any] = Field(
        dict(),
        description="A dictionary of the provenance info used to create this fitting entry.",
    )
    extras: Dict[str, Any] = Field(
        dict(),
        description="Any extra information that might be needed by the target.",
    )
    input_conformers: List[Array[np.ndarray]] = Field(
        ...,
        description="The list of conformers stored as a np.ndarray so we can serialize to json.",
    )
    fragment: bool = Field(
        ..., description="If the molecule is a fragment of a parent."
    )
    fragment_parent_mapping: Optional[Dict[int, int]] = Field(
        None,
        description="If the molecule is a fragment store the fragment to parent mapping here, to use this enter the index of the atom in the fragment to get the corresponding index of the parent atom.",
    )
    error_message: Optional[str] = Field(
        None,
        description="Any errors recorded while generating the fitting data should be listed here.",
    )

    def __init__(self, molecule: off.Molecule, **kwargs):
        """
        Handle the unpacking of the input conformers.
        """
        input_confs = kwargs.get("input_conformers", [])
        if not input_confs:
            # get from the molecule
            for conformer in molecule.conformers:
                input_confs.append(conformer.in_units_of(unit.angstrom))
            kwargs["input_conformers"] = input_confs

        super(FittingTask, self).__init__(**kwargs)

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
        Create just the OpenFF graph molecule representation for the FittingSchema no geometry is included.

        Note:
            This is useful for quick comparsions as the geometry does not have to be built and validated.
        """

        return off.Molecule.from_mapped_smiles(
            self.attributes.canonical_isomeric_explicit_hydrogen_mapped_smiles
        )

    @property
    def initial_molecule(self) -> off.Molecule:
        """
        Create an openFF molecule representation for the FittingSchema with the input geometries.
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
        Get a specific task data that will be combined with general molecule data to make the hash.
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
        Given a single result and a mapping remap the result ordering to match the fitting schema order.

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

    def __eq__(self, other: "FittingTask") -> bool:
        """
        Check if the job hash is the same.
        """
        return self.get_task_hash() == other.get_task_hash()


class TorsionTask(FittingTask):
    """
    A schema detailing a torsiondrive fitting target.
    """

    task_type: Literal["torsion1d"] = "torsion1d"
    dihedrals: Optional[List[Tuple[int, int, int, int]]] = Field(
        None,
        description="The dihedrals which are to be driven during the collection workflow.",
    )
    torsiondrive_data: Optional[List[SingleResult]] = Field(
        None, description="The results of the torsiondrive."
    )

    @validator("dihedrals")
    def _validate_dihedrals(
        cls, dihedrals: Optional[List[Tuple[int, int, int, int]]]
    ) -> Optional[List[Tuple[int, int, int, int]]]:
        """
        Dihedrals targeted for driving and optimization are stored here make sure that only 1D or 2D scans are available.
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
                    f"A maximum of a 2D dihedral scan is supported but a scan of length {len(dihedrals)} was given."
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
        Take a torsiondrive result check if the molecule is the same and the same dihedral is targeted and apply the results.
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
                # work out if the result and schema target the same dihedral via central bond
                dihedral = set(self.dihedrals[0][1:3])
                # now map the result dihedral back
                target_dihedral = [atom_map[i] for i in results.dihedrals[0]]
                if not dihedral.difference(set(target_dihedral[1:3])):
                    # we need to change the target dihedral to match what the result is for
                    self.dihedrals = [
                        target_dihedral,
                    ]
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

                else:
                    raise DihedralSelectionError(
                        f"Molecules are the same but do not target the same dihedral."
                    )
            else:
                raise MoleculeMissMatchError(
                    f"Molecules are not isomorphic and the results can not be transferred."
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
        from openff.bespokefit.utils import get_torsiondrive_index

        # Note we only support 1D scans
        atom_map = dict((atom, i) for i, atom in enumerate(self.dihedrals[0]))
        molecule = self.initial_molecule
        molecule.properties["atom_map"] = atom_map
        index = get_torsiondrive_index(molecule)
        task = self.get_task_hash()
        attributes = self.attributes
        attributes.task_hash = task  # add in the task hash
        new_entry = TorsionDriveEntry(
            index=index,
            off_molecule=molecule,
            attributes=attributes,
            dihedrals=self.dihedrals,
        )
        return new_entry


class OptimizationTask(FittingTask):
    """
    A schema detailing an optimisation fitting target.
    """

    task_type: Literal["optimization"] = "optimization"
    optimization_data: Optional[SingleResult] = Field(
        None,
        description="The results of the optimization which contains the optimised geometry",
    )

    def _get_task_hash(self) -> str:
        return "optimization"

    def get_qcsubmit_task(self) -> OptimizationEntry:
        """
        Generate an optimization entry for the molecule.
        """
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
            index=index, off_molecule=molecule, attributes=attributes
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
        Generate either an optimization task or a hessian single point task based on the progress of the workflow.
        """
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
            index=index, off_molecule=molecule, attributes=attributes
        )
        return new_entry

    def update_with_results(self, result: BasicResult) -> None:
        raise NotImplementedError()

    def reference_data(self) -> SingleResult:
        return self.hessian_data

    @property
    def collected(self) -> bool:
        return True if self.hessian_data is not None else False


class TargetSchema(SchemaBase):
    """
    This is the target schema which should tell the optimizer what targets should be optimized with the collected
    data listed here.
    """

    target_name: str = Field(
        ..., description="The name of the registered target that is to be optimized."
    )
    provenance: Dict[str, Any] = Field(
        ...,
        description="The run time dependencies of the target.",
    )
    settings: Dict[str, Any] = Field(
        ..., description="The run time settings for this target that should be loaded."
    )
    qc_spec: QCSpec = Field(
        ...,
        description="The qc specification that should be used to collect the reference data.",
    )
    collection_workflow: Literal["torsion1d", "optimization", "hessian"] = Field(
        ..., description="The collection workflow used to gather the reference data."
    )
    tasks: List[Union[TorsionTask, OptimizationTask, HessianTask]] = Field(
        [],
        description="The list of fitting tasks that this target will include for optimization.",
    )

    @property
    def n_tasks(self) -> int:
        """Get the number of tasks for this target."""
        return len(self.tasks)

    def add_fitting_task(
        self, task: Union[TorsionTask, OptimizationTask, HessianTask]
    ) -> None:
        """
        Add a fitting task if it has not already been specified, the task must match the collection workflow.
        """

        if task.task_type != self.collection_workflow:
            raise TaskMissMatchError(
                f"A {task.task_type} task can not be put into a {self.collection_workflow} collection workflow."
            )
        if task not in self.tasks:
            # we need to make sure the name has the correct index.
            no = len(self.tasks)
            task.name = f"-{self.collection_workflow}-{no}"
            self.tasks.append(task)

    @property
    def ready_for_fitting(self) -> bool:
        """
        A self validation method which makes sure all fitting tasks are ready before fitting the target.
        """
        for task in self.tasks:
            if not task.collected:
                return False
        return True

    def get_task_map(
        self,
    ) -> Dict[str, List[Union[TorsionTask, OptimizationTask, HessianTask]]]:
        """
        Generate a mapping between all current tasks and their task hash.
        """

        hash_map = dict()
        for task in self.tasks:
            if not task.collected:
                task_hash = task.get_task_hash()
                hash_map.setdefault(task_hash, []).append(task)
        return hash_map

    def compare_qcspec(self, result) -> bool:
        """
        Make sure the qcspec from the results match the targeted qcspec.
        """
        if (
            result.program.lower() == self.qc_spec.program.lower()
            and result.method.lower() == self.qc_spec.method.lower()
            and result.basis.lower() == self.qc_spec.basis.lower()
            if result.basis is not None
            else result.basis == self.qc_spec.basis
        ):
            return True
        else:
            return False

    def get_qcsubmit_tasks(
        self,
    ) -> List[Union[TorsionDriveEntry, OptimizationEntry, DatasetEntry]]:
        """
        Gather the qcsubmit tasks for the entries in this target.
        Make sure we deduplicate the jobs which should make it easier to build the dataset.
        """
        tasks = {}
        for task in self.tasks:
            job = task.get_qcsubmit_task()
            if job.attributes.task_hash not in tasks:
                tasks[job.attributes.task_hash] = job
        return list(tasks.values())

    def build_qcsubmit_dataset(
        self,
    ) -> Union[OptimizationDataset, TorsiondriveDataset, BasicDataset]:
        """
        Build a qcsubmit dataset from the qcsubmit tasks associated with this target and collection type.
        """
        description = "A bespoke-fit generated dataset to be used for parameter optimization for more information please visit https://github.com/openforcefield/bespoke-fit."
        dataset_name = "OpenFF Bespoke-fit"
        if self.collection_workflow == "torsion1d":
            dataset = TorsiondriveDataset(
                dataset_name=dataset_name,
                qc_specifications={},
                description=description,
                driver="gradient",
            )
        elif self.collection_workflow == "optimization":
            dataset = OptimizationDataset(
                dataset_name=dataset_name,
                qc_specifications={},
                description=description,
                driver="gradient",
            )
        elif self.collection_workflow == "hessian":
            dataset = BasicDataset(
                dataset_name=dataset_name,
                qc_specifications={},
                description=description,
                driver="hessian",
            )
        else:
            raise NotImplementedError(
                f"The collection workflow {self.collection_workflow} does not have a supported qcsubmit dataset type."
            )
        # update the metadata url
        dataset.metadata.long_description_url = (
            "https://github.com/openforcefield/bespoke-fit"
        )
        # set the qc_spec
        dataset.add_qc_spec(**self.qc_spec.dict())
        # now add each task
        tasks = self.get_qcsubmit_tasks()
        for task in tasks:
            dataset.dataset[task.index] = task
            # we also need to update the elements metadata
            # TODO add an api point to qcsubmit to allow adding dataset entries, this would also
            # validate the entry type.
            dataset.metadata.elements.update(task.initial_molecules[0].symbols)

        return dataset

    def update_with_results(
        self,
        results: Union[
            BasicCollectionResult,
            OptimizationCollectionResult,
            TorsionDriveCollectionResult,
        ],
    ) -> None:
        """
        Take a list of results and work out if they can be mapped on the the target.
        """
        # make sure the result type matches the collection workflow allowed types
        if (
            isinstance(results, TorsionDriveCollectionResult)
            and self.collection_workflow != "torsion1d"
        ):
            raise Exception("Torsion1d workflow requires torsiondrive results.")
        elif (
            not isinstance(results, TorsionDriveCollectionResult)
            and self.collection_workflow == "torsion1d"
        ):
            raise Exception(
                "Optimization and hessian workflows require optimization and basic dataset results"
            )
        elif (
            isinstance(results, BasicCollectionResult)
            and results.driver != self.collection_workflow
        ):
            raise Exception(
                "Hessian results must be computed using the hessian driver."
            )

        # check the QC method matches what we targeted
        if not self.compare_qcspec(results):
            raise Exception(
                "The results could not be saved as the qcspec did not match"
            )

        # we now know the specification and result type match so try and apply the results
        for result in results.collection.values():
            for task in self.tasks:
                try:
                    task.update_with_results(result)
                except (DihedralSelectionError, MoleculeMissMatchError):
                    continue
            else:
                continue


class FragmentSchema(SchemaBase):
    """
    A basic data class which records the relation betweent parent and a fragment.
    """

    parent_torsion: Tuple[int, int] = Field(
        ...,
        description="The target torsion in the parent molecule which was fragmented around.",
    )
    fragment_torsion: Tuple[int, int] = Field(
        ...,
        description="The corresponding indices of the fragment torsion which maps to the parent torsion.",
    )
    fragment_attributes: MoleculeAttributes = Field(
        ..., description="The full set of cmiles descriptors for this molecule."
    )
    fragment_parent_mapping: Dict[int, int] = Field(
        ...,
        description="The mapping from the fragment to the parent atoms, so fragment_parent_mapping[i] would give the index of the atom in the parent which is equivalent to atom i.",
    )

    @property
    def molecule(self) -> off.Molecule:
        """Build the graph of the fragment molecule"""
        return off.Molecule.from_mapped_smiles(
            self.fragment_attributes.canonical_isomeric_explicit_hydrogen_mapped_smiles
        )

    @property
    def target_dihedral(self) -> Tuple[int, int, int, int]:
        """
        Return a target dihedral that could be driven for the target central bond.
        """
        from openff.bespokefit.smirks import SmirksGenerator

        dihedrals = SmirksGenerator.get_all_torsions(
            bond=self.fragment_torsion, molecule=self.molecule
        )
        molecule = self.molecule
        # now find the first dihedral with no hydrogens,
        # if none can be found return any
        for dihedral in dihedrals:
            atoms = [molecule.atoms[i].atomic_number for i in dihedral]
            if 1 not in atoms:
                return dihedral

        return dihedrals[0]


class MoleculeSchema(SchemaBase):
    """
    This is the main fitting schema which wraps a molecule object with settings and information about the target to be
    fit and the reference data.
    """

    attributes: MoleculeAttributes = Field(
        ...,
        description="The full set of molecule cmiles descriptors which can be used to build the molecule.",
    )
    task_id: str = Field(
        ...,
        description="An id given to the parameterization of this molecule to separate when multiple molecules are to be parameterized separately.",
    )
    fragment_data: Optional[List[FragmentSchema]] = Field(
        None, description="The list of fragment which corespond to this molecule."
    )
    fragmentation_engine: Optional[Dict[str, Any]] = Field(
        None,
        description="The fragmentation engine and settings used to fragment this molecule.",
    )

    @property
    def molecule(self) -> off.Molecule:
        """
        Get the openff molecule representation of the input target molecule.
        """
        return off.Molecule.from_mapped_smiles(
            self.attributes.canonical_isomeric_explicit_hydrogen_mapped_smiles
        )

    @property
    def fragments(self) -> List[off.Molecule]:
        """
        Get a unique list of the fragments in this molecule.
        """
        unique_mols = []
        for fragment in self.fragment_data:
            fragment_mol = fragment.molecule
            if fragment_mol not in unique_mols:
                unique_mols.append(fragment_mol)
        return unique_mols

    def add_fragment(self, fragment: FragmentSchema) -> None:
        """
        Add a new fragment schema to this molecule.
        """
        if self.fragment_data is None:
            self.fragment_data = []
        self.fragment_data.append(fragment)


class OptimizationSchema(SchemaBase):
    """
    This class collects together an optimizer with its targets and the tasks.
    """

    initial_forcefield: str = Field(
        ..., description="The initial Forcefield that should then be optimized"
    )
    optimizer_name: str = Field(
        ...,
        description="The name of the registered optimizer used for this set of targets.",
    )
    settings: Dict[str, Any] = Field(
        ...,
        description="The run time settings for this optimizer which is used to rebuild the class.",
    )
    job_id: str = Field(
        ..., description="The unique job id given to this optimization task."
    )
    targets: List[TargetSchema] = Field(
        [],
        description="The list of registered targets which will be optimized simultaneously by this optimizer.",
    )
    status: Status = Field(
        Status.Prepared,
        description="The enum declaring the current status of this optimization.",
    )
    target_smirks: List[
        Union[AtomSmirks, BondSmirks, AngleSmirks, TorsionSmirks]
    ] = Field(
        [],
        description="A List of all of the target smirks that should be optimised.",
    )
    final_smirks: Optional[
        List[Union[AtomSmirks, BondSmirks, AngleSmirks, TorsionSmirks]]
    ] = Field(None, description="The final set of smirks after optimisation.")
    target_parameters: SmirksSettings = Field(
        ...,
        description="The set of specific parameters that should be optimmized such as bond length.",
    )
    target_molecule: MoleculeSchema = Field(
        ...,
        description="The target molecule is defined along with information about its fragments.",
    )

    @property
    def n_tasks(self) -> int:
        """
        Calculate the number of unique tasks to be currently computed
        """
        return len(self.task_hashes)

    @property
    def task_hashes(self) -> List[str]:
        """
        Compute the task hashes for this molecule.
        """
        task_hash = set()

        for target in self.targets:
            for task in target.tasks:
                task_hash.add(task.get_task_hash())
        return list(task_hash)

    @property
    def n_targets(self) -> int:
        """
        Calculate the number of targets to be fit for this molecule.
        """

        return len(self.targets)

    @property
    def ready_for_fitting(self) -> bool:
        """
        Calculate if the targets for this optimizer are ready to be fit.
        """

        for target in self.targets:
            if not target.ready_for_fitting:
                return False
        return True

    def get_final_forcefield(
        self,
        generate_bespoke_terms: bool = True,
        drop_out_value: Optional[float] = None,
    ) -> ForceField:
        """
        Generate the final bespoke forcefield for this molecule by collecting together all optimized smirks.

        Note:
            It is know that when creating fitting smirks for the fragments that they can hit unintended dihedrals in other fragments if they are similar during fitting. To ensure the correct parameters are used in their intended positions
            on the parent molecule each fragment is typed with the fitting forcefield and parameters again and a new bespoke term for the parent is made which uses the same parameters.

        Parameters:
            generate_bespoke_terms: If molecule specific bespoke terms should be made, this is recommended as some fragment smirks patterns may not transfer back to the parent correctly due to fragmentation.
            drop_out_value: Any torsion force constants below this value will be dropped as they are probably negligible.
        """
        # TODO change this to a util function remove from target base class

        # check that all optimizations are finished
        if self.status != Status.Complete:
            raise OptimizerError(
                f"The molecule has not completed all optimization stages which are required to generate the final forcefield."
            )
        if self.final_smirks is None:
            raise OptimizerError(
                f"The optimization status is complete but no optimized smirks were found."
            )
        from openff.bespokefit.forcefield_tools import ForceFieldEditor

        # get all of the target smirks
        target_smirks = self.final_smirks
        # build the parent molecule
        parent_molecule = self.target_molecule.molecule

        if drop_out_value is not None:
            # loop over all of the target smirks and drop and torsion k values lower than the drop out
            for smirk in target_smirks:
                if smirk.type == SmirksType.ProperTorsions:
                    # keep a list of terms to remove
                    to_remove = []

                    for p, term in smirk.terms.items():
                        if abs(float(term.k.split("*")[0])) < drop_out_value:
                            to_remove.append(p)

                    # now remove the low values
                    for p in to_remove:
                        del smirk.terms[p]

        # the final fitting force field should have all final smirks propagated through
        fitting_ff = ForceFieldEditor(forcefield_name=self.initial_forcefield)
        fitting_ff.add_smirks(smirks=target_smirks, parameterize=False)

        # here we type the fragment with the final forcefield and then build a bespoke dihedral term for the parent
        # to hit the atoms that map from the fragment to the parent
        # we do not modify any other smirks types but this needs testing to make sure that they do transfer.
        if generate_bespoke_terms:
            bespoke_smirks = []
            # get a list of unique fragments and all of the torsions that have been targeted
            for target in self.targets:
                if target.collection_workflow == "torsion1d":
                    for task in target.tasks:
                        # check if the smirks are from a fragment
                        if task.fragment:
                            new_smirks = self._generate_bespoke_torsions(
                                forcefield=fitting_ff,
                                parent_molecule=parent_molecule,
                                task_data=task,
                            )
                            bespoke_smirks.extend(new_smirks)

            # make a new ff object with the new terms
            bespoke_ff = ForceFieldEditor(forcefield_name=self.initial_forcefield)
            # get a list of non torsion smirks
            new_smirks = [
                smirk
                for smirk in target_smirks
                if smirk.type != SmirksType.ProperTorsions
            ]
            new_smirks.extend(bespoke_smirks)
            bespoke_ff.add_smirks(smirks=new_smirks, parameterize=False)
            return bespoke_ff.forcefield

        else:
            return fitting_ff.forcefield

    def _generate_bespoke_torsions(
        self,
        forcefield: "ForceFieldEditor",
        parent_molecule: off.Molecule,
        task_data: TorsionTask,
    ) -> List[TorsionSmirks]:
        """
        For the given task generate set of bespoke torsion terms for the parent molecule using all layers. Here we have to type the fragment and use the fragment parent mapping
        to transfer the parameters.
        """
        from openff.bespokefit.smirks import SmirksGenerator

        smirks_gen = SmirksGenerator(
            target_smirks=[SmirksType.ProperTorsions],
            layers="all",
            expand_torsion_terms=False,
        )

        fragment = task_data.graph_molecule
        fragment_parent_mapping = task_data.fragment_parent_mapping
        # label the fitting molecule
        labels = forcefield.label_molecule(molecule=fragment)["ProperTorsions"]

        bespoke_torsions = []
        for bond in task_data.central_bonds:
            fragment_dihedrals = smirks_gen.get_all_torsions(
                bond=bond, molecule=fragment
            )
            for dihedral in fragment_dihedrals:
                # get the smirk that hit this torsion
                off_smirk = labels[dihedral]
                # work out the parent torsion
                parent_torsion = tuple([fragment_parent_mapping[i] for i in dihedral])
                # make the bespoke smirks
                smirks = smirks_gen._get_new_single_graph_smirks(
                    atoms=parent_torsion, molecule=parent_molecule
                )
                # make the new Torsion Smirks
                bespoke_smirk = TorsionSmirks(smirks=smirks)
                bespoke_smirk.update_parameters(off_smirk=off_smirk)
                if bespoke_smirk not in bespoke_torsions:
                    bespoke_torsions.append(bespoke_smirk)

        return bespoke_torsions

    @property
    def parameterize_smirks(
        self,
    ) -> List[Union[AtomSmirks, BondSmirks, AngleSmirks, TorsionSmirks]]:
        """
        For the set of target smirks use the parameter targets to tag the values which should be optimized.
        For example a BondSmirks with a parameter target of BondLength will have length set to be parameterized.
        """
        import copy

        target_smirks = copy.deepcopy(self.target_smirks)
        for target_parameter in self.target_parameters:
            for smirk in target_smirks:
                if (
                    target_parameter.parameter_type == smirk.type
                    and target_parameter.parameter_type == SmirksType.ProperTorsions
                ):
                    smirk.parameterize = target_parameter.k_values
                elif target_parameter.parameter_type == smirk.type:
                    smirk.parameterize.add(target_parameter.target)
        return target_smirks

    def get_fitting_forcefield(self) -> ForceField:
        """
        Take the initial forcefield and edit it to add the new terms and return the OpenFF FF object.

        Parameters:
            initial_forcefield: The name of the initial Forcefield we will be starting at.
        """
        from openff.bespokefit.forcefield_tools import ForceFieldEditor

        # get all of the new target smirks
        target_smirks = self.parameterize_smirks
        ff = ForceFieldEditor(self.initial_forcefield)
        ff.add_smirks(target_smirks, parameterize=True)
        # if there are any parameters from a different optimization stage add them here without parameterize tags
        return ff.forcefield

    def dict(self, *args, **kwargs):
        data = super().dict()
        data["status"] = self.status.value
        return data

    def update_with_results(
        self,
        results: Union[
            BasicCollectionResult,
            OptimizationCollectionResult,
            TorsionDriveCollectionResult,
        ],
    ) -> None:
        """
        Take a list of results and search through the entries for a match where the results can be transferred.
        """
        for target in self.targets:
            target.update_with_results(results)

        if self.ready_for_fitting:
            self.status = Status.Ready

    def get_task_map(
        self,
    ) -> Dict[str, List[Union[TorsionTask, OptimizationTask, HessianTask]]]:
        """
        Generate a mapping between all of the current tasks and their collection workflow stage.
        """
        hash_map = dict()
        for target in self.targets:
            target_map = target.get_task_map()
            for key, tasks in target_map.items():
                hash_map.setdefault(key, []).extend(tasks)

        return hash_map

    def build_qcsubmit_datasets(
        self,
    ) -> List[Union[TorsiondriveDataset, OptimizationDataset, BasicDataset]]:
        """
        For each of the targets build a qcsubmit dataset of reference collection tasks.
        """
        datasets = [target.build_qcsubmit_dataset() for target in self.targets]
        return datasets

    def add_target(self, target: TargetSchema) -> None:
        """
        Add a target schema to the optimizer making sure this target is registered with the optimizer.
        """
        from openff.bespokefit.optimizers import get_optimizer

        opt = get_optimizer(optimizer_name=self.optimizer_name)
        if target.target_name.lower() in opt.get_registered_target_names():
            self.targets.append(target)


class FittingSchema(SchemaBase):
    """
    This is the main fitting schema which can be consumed by bespokefit in order to be executed.
    """

    client: str = Field(
        "snowflake",
        description="The type of QCArchive server that will be used, snowflake/snowflake_notebook is a temperary local server that spins up temp compute but can connect to a static server.",
    )
    optimizer_settings: Dict[str, Dict[str, Any]] = Field(
        dict(),
        description="A dictionary containing all run time settings for each optimizer in the workflow so that they can be rebuilt when optimization tasks are generated.",
    )
    target_settings: Dict[str, Dict[str, Any]] = Field(
        dict(),
        description="A dictonary containing all of the run time settings for each of the targets in the pipeline, they will be used to build each target.",
    )
    tasks: List[OptimizationSchema] = Field(
        [],
        description="The list of optimization tasks to be carried out in the fitting procedure.",
    )

    @classmethod
    def parse_file(
        cls: Type["Model"],
        path: Union[str, Path],
        *,
        content_type: str = None,
        encoding: str = "utf8",
        proto: Protocol = None,
        allow_pickle: bool = False,
    ) -> "Model":
        data = deserialize(file_name=path)
        return cls(**data)

    def add_optimizer(self, optimizer: "Optimizer") -> None:
        """
        Add a valid optimizer to the fitting schema.
        """
        from openff.bespokefit.optimizers import list_optimizers

        if optimizer.optimizer_name.lower() in list_optimizers():
            if optimizer.optimizer_name not in self.optimizer_settings:
                self.optimizer_settings[
                    optimizer.optimizer_name.lower()
                ] = optimizer.dict(exclude={"optimization_targets"})
            # now we need to store the target settings
            for target in optimizer.optimization_targets:
                self.target_settings[target.name] = target.dict()
        else:
            raise OptimizerError(
                f"The given optimizer {optimizer.optimizer_name} has not been registered with bespokefit, please register first."
            )

    @property
    def get_optimizers(self) -> List["Optimizer"]:
        """
        Get all of the optimizers from the settings.
        """
        from ..optimizers import get_optimizer

        return list(
            get_optimizer(**settings) for settings in self.optimizer_settings.values()
        )

    def get_optimizer(self, optimizer_name: str) -> "Optimizer":
        """
        Get the requested optimizer with correct settings from the optimizer list.
        """
        optimizers = self.get_optimizers
        for opt in optimizers:
            if optimizer_name.lower() == opt.optimizer_name.lower():
                return opt
        raise OptimizerError(
            f"An optimizer with the name {optimizer_name} can not be found in the current list of optimizers {self.optimizer_names}"
        )

    @property
    def optimizer_names(self) -> List[str]:
        """
        Get a list of the optimizers in the workflow schema.
        """
        return list(self.optimizer_settings.keys())

    def add_optimization_task(self, optimization_task: OptimizationSchema) -> None:
        """
        Add a complete molecule schema to the fitting schema.
        """
        # we have to make sure that the optimizer has also been added to the schema.
        assert optimization_task.optimizer_name.lower() in self.optimizer_names
        self.tasks.append(optimization_task)

    def export_schema(self, file_name: str) -> None:
        """
        Export the fitting schema to file.
        """

        if "json" in file_name:
            serialize(self, file_name=file_name)
        else:
            raise RuntimeError("The given file type is not supported please used json.")

    @property
    def n_molecules(self) -> int:
        """
        Calculate the number of initial molecules to be optimized.
        """

        return len(self.tasks)

    @property
    def task_hashes(self) -> List[str]:
        """
        Get all of the unique task hashes.
        """
        tasks = set()
        for task in self.tasks:
            tasks.update(task.task_hashes)
        return list(tasks)

    @property
    def n_tasks(self) -> int:
        """
        Calculate the number of unique QM tasks to be computed.
        """

        return len(self.task_hashes)

    def update_with_results(
        self,
        results: Union[
            BasicCollectionResult,
            OptimizationCollectionResult,
            TorsionDriveCollectionResult,
        ],
    ) -> None:
        """
        Take a list of results and try to apply them to each of the molecules in the fitting schema.
        """
        for task in self.tasks:
            task.update_with_results(results)

    def generate_qcsubmit_datasets(
        self,
    ) -> List[Union[BasicDataset, OptimizationDataset, TorsiondriveDataset]]:
        """
        Generate a set of qcsubmit datasets containing all of the tasks required to compute the QM data.

        Note:
            Hessian datasets can not be produced until the initial optimization is complete
            The task hash will also be embedded into the entry to make updating the results faster.
        """
        # group the datasets by type
        all_datasets = {}
        for task in self.tasks:
            datasets = task.build_qcsubmit_datasets()
            for dataset in datasets:
                all_datasets.setdefault(dataset.dataset_type, []).append(dataset)

        # now we want to do dataset adding for each type
        final_datasets = []
        for datasets in list(all_datasets.values()):
            master_dataset = datasets.pop()
            for dataset in datasets:
                master_dataset += dataset
            final_datasets.append(master_dataset)

        return final_datasets

    @property
    def molecules(self) -> List[off.Molecule]:
        """
        Return an openforcefield representation of each of the target molecules in the fitting schema.
        """
        return [task.target_molecule.molecule for task in self.tasks]

    @property
    def entry_molecules(self) -> List[off.Molecule]:
        """
        Generate a list of unique molecules which we have collection tasks for these are not always the same as the target molecules due to fragmentation.
        """
        unique_molecules = set()
        for task in self.tasks:
            fragments = task.target_molecule.fragments
            unique_molecules.update(fragments)

        return list(unique_molecules)
