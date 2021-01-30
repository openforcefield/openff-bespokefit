import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import numpy as np
from openforcefield import topology as off
from openforcefield.typing.engines.smirnoff import ForceField
from pydantic import Field, Protocol, validator
from qcelemental.models.types import Array
from simtk import unit

from openff.bespokefit.collection_workflows import (
    CollectionMethod,
    Precedence,
    WorkflowStage,
)
from openff.bespokefit.common_structures import SchemaBase, Status, Task
from openff.bespokefit.exceptions import (
    DihedralSelectionError,
    MissingReferenceError,
    MissingWorkflowError,
    MoleculeMissMatchError,
    OptimizerError,
    WorkflowUpdateError,
)
from openff.bespokefit.schema.smirks import (
    AngleSmirks,
    AtomSmirks,
    BondSmirks,
    SmirksSchema,
    TorsionSmirks,
    ValidatedSmirks,
)
from openff.bespokefit.utils import schema_to_datasets
from openff.qcsubmit.common_structures import MoleculeAttributes, QCSpec
from openff.qcsubmit.datasets import (
    BasicDataset,
    OptimizationDataset,
    TorsiondriveDataset,
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


class FittingEntry(SchemaBase):
    """
    This is the fitting schema which has instructions on how to collect the reference data and fit the parameters for a molecule.
    """

    name: str = Field(
        ...,
        description="The name of the fitting entry, this is normally the molecule name and task which generates the input data like torsiondrive.",
    )
    attributes: MoleculeAttributes = Field(
        ...,
        description="A dictionary containing the cmiles information about the molecule.",
    )
    collection_workflow: List[WorkflowStage] = Field(
        [],
        description="The list of data generation jobs to be completed in order.",
    )
    target_smirks: List[Union[SmirksSchema, ValidatedSmirks]] = Field(
        [],
        description="The list of target smirks this entry should exercise in optimization.",
    )
    qc_spec: QCSpec = Field(
        QCSpec(),
        description="The QCSubmit style specification which should be used to collect the reference data.",
    )
    provenance: Dict[str, Any] = Field(
        dict(),
        description="A dictionary of the provenance info used to create this fitting entry.",
    )
    dihedrals: Optional[List[Tuple[int, int, int, int]]] = Field(
        None,
        description="The dihedrals which are to be driven during the collection workflow.",
    )
    extras: Dict[str, Any] = Field(
        dict(),
        description="Any extra information that might be needed by the target.",
    )
    input_conformers: List[Array[np.ndarray]] = Field(
        [],
        description="The list of conformers stored as a np.ndarray so we can serialize to json.",
    )
    fragment: bool = Field(
        ..., description="If the molecule is a fragment of a parent."
    )
    fragment_parent_mapping: Optional[Dict[int, int]] = Field(
        None,
        description="If the molecule is a fragment store the fragment to parent mapping here, to use this enter the index of the atom in the fragment to get the corresponding index of the parent atom.",
    )

    @validator("target_smirks", pre=True)
    def _check_target_smirks(cls, smirks):
        """
        A helper method to correctly handle the union of types.
        """
        new_smirks = []
        _type_conversion = {
            "vdW": AtomSmirks,
            "Bonds": BondSmirks,
            "Angles": AngleSmirks,
            "ProperTorsions": TorsionSmirks,
        }
        for smirk in smirks:
            if isinstance(smirk, dict):
                # if it is a dict from importing unpack here
                new_smirk = _type_conversion[smirk["type"]](**smirk)
                new_smirks.append(new_smirk)
            else:
                new_smirks.append(smirk)

        return new_smirks

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

    @property
    def current_molecule(self) -> off.Molecule:
        """
        Create an openFF molecule representation for the FittingSchema with the latest geometries from the results.
        """
        # get the initial molecule
        off_mol = self.initial_molecule
        # now workout if there are any new geometries
        for stage in self.collection_workflow:
            if stage.status == Status.Complete:
                geometries = stage.get_result_geometries()
                off_mol._conformers = []
                for geometry in geometries:
                    off_mol.add_conformer(geometry)
        return off_mol

    def add_target_smirks(
        self, smirks: Union[AtomSmirks, BondSmirks, AngleSmirks, TorsionSmirks]
    ) -> None:
        """
        Add a smirks schema to list this method also makes sure the smirks is not already registered and deduplicates the smirks entries.
        """

        for target in self.target_smirks:
            if target == smirks:
                # we need to just transfer the atoms if the patterns are the same
                target.atoms.update(smirks.atoms)
                # we also need to take the pattern with the most or terms
                if len(smirks.smirks) > len(target.smirks):
                    target.smirks = smirks.smirks
                break
        else:
            self.target_smirks.append(smirks)

    def current_tasks(self) -> List[WorkflowStage]:
        """
        Get the current task to be executed with its hash added to it.
        """
        tasks = []
        for i, stage in enumerate(self.collection_workflow):
            if stage.status != Status.Complete:
                job_id = self.get_task_hash(stage)
                stage.job_id = job_id
                tasks.append(stage)
                # if the task can be done in parallel return the other tasks
                if stage.precedence == Precedence.Parallel:
                    for parallel_stage in self.collection_workflow[i + 1 :]:
                        if parallel_stage.precedence == Precedence.Parallel:
                            job_id = self.get_task_hash(parallel_stage)
                            parallel_stage.job_id = job_id
                            tasks.append(parallel_stage)
                return tasks
        return []

    def get_task_hash(self, stage: WorkflowStage) -> str:
        """
        Generate a task hash for the metadata and collection stage combination.
        """
        m = hashlib.sha1()
        hash_string = self._get_general_hash_data() + self._get_stage_hash_data(stage)
        m.update(hash_string.encode("utf-8"))
        return m.hexdigest()

    def _get_general_hash_data(self) -> str:
        """
        Collect the general hash data.
        """
        inchi = self.initial_molecule.to_inchikey(
            fixed_hydrogens=True
        )  # non standard inchi
        hash_string = (
            inchi + self.qc_spec.method + str(self.qc_spec.basis) + self.qc_spec.program
        )
        return hash_string

    def _get_stage_hash_data(self, stage: WorkflowStage) -> str:
        """
        Get the data from a collection stage read for hashing.
        """
        if stage.method.value == "local":
            # we need to specify the target method as well
            target_data = stage.method.value + self.provenance["target"]
        elif stage.method.value == "torsiondrive1d":
            # we also need to add the dihedrals
            dihedral = str(self.dihedrals)
            target_data = stage.method.value + dihedral
        else:
            target_data = stage.method.value

        return target_data

    def get_hash(self):
        """
        Get a hash of the Fitting entry including all tasks in the collection workflow used when constructing a
        deduplicated queue of collection tasks.
        """

        m = hashlib.sha1()
        hash_string = self._get_general_hash_data()
        for stage in self.collection_workflow:
            target_data = self._get_stage_hash_data(stage)
            hash_string += target_data

        m.update(hash_string.encode("utf-8"))
        return m.hexdigest()

    def __eq__(self, other: "FittingEntry") -> bool:
        """
        Check if the job hash is the same.
        """
        return self.get_hash() == other.get_hash()

    def get_reference_data(self) -> List[SingleResult]:
        """
        Return the final result of the collection workflow if it is set else raise an error.
        """
        if self.collection_workflow:
            result = self.collection_workflow[-1].result
            if result is not None:
                return result
            else:
                raise MissingReferenceError(
                    f"The workflow has not collected any results yet."
                )
        else:
            raise MissingWorkflowError(
                f"The Entry has no collection workflow to hold results."
            )

    @property
    def ready_for_fitting(self) -> bool:
        """
        A self validation method to make sure the molecule is ready for fitting.

        Returns:
            `True` if all information is present else `False`.
        """
        # check the last stage is ready for fitting
        if self.collection_workflow:
            stage = self.collection_workflow[-1]
            if stage.status == Status.Complete and stage.result is not None:
                return True

        return False

    def update_with_results(
        self, results: Union[BasicResult, TorsionDriveResult, OptimizationEntryResult]
    ) -> None:
        """
        This will update the fitting entry with results collected with qcsubmit, the type of data accepted depends here on the collection method specified.
        """
        # TODO how can we accept other input types?

        for stage in self.collection_workflow:
            if stage.method in [
                CollectionMethod.TorsionDrive1D,
                CollectionMethod.TorsionDrive2D,
                CollectionMethod.Optimization,
            ]:
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

                            stage.result = new_results
                            stage.status = Status.Complete

                        else:
                            raise DihedralSelectionError(
                                f"Molecules are the same but do not target the same dihedral."
                            )
                    else:
                        raise MoleculeMissMatchError(
                            f"Molecules are not isomorphic and the results can not be transferred."
                        )

                else:
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
        description="The run time settings for the target, these include settings made to generate each fitting entry.",
    )
    entries: List[FittingEntry] = Field(
        [],
        description="The list of fitting entries that this target will include for optimization, each also detail how the input data will be generated.",
    )

    def add_fitting_entry(self, entry: FittingEntry) -> None:
        """
        Add a fitting entry if it has not already been specified.
        """

        if entry not in self.entries:
            # we need to make sure the name has the correct index.
            no = len(self.entries)
            entry.name += f"-{entry.collection_workflow[-1].method.value}-{no}"
            self.entries.append(entry)

    def get_target_smirks(self) -> List[SmirksSchema]:
        """
        Generate a deduplicated list of all of the new target smirks from the entries for this target.
        """
        target_smirks = []
        for entry in self.entries:
            for smirk in entry.target_smirks:
                if smirk not in target_smirks:
                    target_smirks.append(smirk)
        return target_smirks

    @property
    def ready_for_fitting(self) -> bool:
        """
        A self validation method which makes sure all fitting entries are ready before fitting the target.
        """
        for entry in self.entries:
            if not entry.ready_for_fitting:
                return False
        return True

    def get_task_map(self) -> Dict[str, List[Task]]:
        """
        Generate a mapping between all current tasks and their collection workflow stage.
        """

        hash_map = dict()
        for entry in self.entries:
            tasks = entry.current_tasks()
            for task in tasks:
                hash_map.setdefault(task.job_id, []).append(
                    Task(entry=entry, collection_stage=task)
                )
        return hash_map

    def update_with_results(
        self,
        results: List[
            Union[
                BasicCollectionResult,
                OptimizationCollectionResult,
                TorsionDriveCollectionResult,
            ]
        ],
    ) -> None:
        """
        Take a list of results and work out if they can be mapped on the the target.
        """
        for result in results:
            if isinstance(result, TorsionDriveCollectionResult):
                # now work out if they can be mapped.
                for td_result in result.collection.values():
                    for entry in self.entries:
                        if (
                            result.program.lower() == entry.qc_spec.program.lower()
                            and result.method.lower() == entry.qc_spec.method.lower()
                            and result.basis.lower() == entry.qc_spec.basis.lower()
                            if result.basis is not None
                            else result.basis == entry.qc_spec.basis
                        ):
                            try:
                                entry.update_with_results(td_result)
                            except (DihedralSelectionError, MoleculeMissMatchError):
                                continue
                        else:
                            continue
            else:
                raise NotImplementedError()


class OptimizationSchema(SchemaBase):
    """
    This class collects together an optimizer with its targets and the entries.
    """

    optimizer_name: str = Field(
        ...,
        description="The name of the registered optimizer used for this set of targets.",
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
    extra_parameters: List[
        Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]
    ] = Field(
        [],
        description="Any extra smirks parameters that should be put into the forcefield but are not to be optimized.",
    )

    @property
    def ready_for_fitting(self) -> bool:
        """
        Calculate if the targets for this optimizer are ready to be fit.
        """

        for target in self.targets:
            if not target.ready_for_fitting:
                return False
        return True

    @property
    def target_smirks(
        self,
    ) -> List[SmirksSchema]:
        """
        Get a deduplicated list of all of the smirks targeted by the optimization targets which are part of this workflow.
        """
        target_smirks = []
        for target in self.targets:
            for smirk in target.get_target_smirks():
                if smirk not in target_smirks:
                    target_smirks.append(smirk)
        return target_smirks

    def update_target_smirks(
        self, smirks: List[Union[BondSmirks, AngleSmirks, TorsionSmirks, AtomSmirks]]
    ):
        """
        Given a list of smirks with current parameters insert them back into the correct fitting entry.

        Parameters:
            smirks: A list of the smirks types with parameters that should be inserted back into the fitting entry.
        """
        for target in self.targets:
            for entry in target.entries:
                new_smirks = []
                for smirk in entry.target_smirks:
                    if smirk in smirks:
                        # the smirks match so transfer the parameters back to the entry
                        location = smirks.index(smirk)
                        new_smirks.append(smirks[location])
                    else:
                        new_smirks.append(smirk)
                # now update the list
                entry.target_smirks = new_smirks

    def get_fitting_forcefield(self, initial_forcefield: str) -> ForceField:
        """
        Take the initial forcefield and edit it to add the new terms and return the OpenFF FF object.

        Parameters:
            initial_forcefield: The name of the initial Forcefield we will be starting at.
        """
        from openff.bespokefit.forcefield_tools import ForceFieldEditor

        # get all of the new target smirks
        target_smirks = self.target_smirks
        ff = ForceFieldEditor(initial_forcefield)
        ff.add_smirks(target_smirks, parameterize=True)
        # if there are any parameters from a different optimization stage add them here without parameterize tags
        if self.extra_parameters:
            ff.add_smirks(self.extra_parameters, parameterize=False)
        return ff.forcefield

    def dict(self, *args, **kwargs):
        data = super().dict()
        data["status"] = self.status.value
        return data

    def update_with_results(
        self,
        results: List[
            Union[
                BasicCollectionResult,
                OptimizationCollectionResult,
                TorsionDriveCollectionResult,
            ]
        ],
    ) -> None:
        """
        Take a list of results and search through the entries for a match where the results can be transferred.
        """
        for target in self.targets:
            target.update_with_results(results)

        if self.ready_for_fitting:
            self.status = Status.Ready

    def get_task_map(self) -> Dict[str, List[Task]]:
        """
        Generate a mapping between all of the current tasks and their collection workflow stage.
        """
        hash_map = dict()
        for target in self.targets:
            target_map = target.get_task_map()
            for key, tasks in target_map.items():
                hash_map.setdefault(key, []).extend(tasks)

        return hash_map


class MoleculeSchema(SchemaBase):
    """
    This is the main fitting schema which wraps a molecule object with settings and information about the target to be
    fit and the reference data.
    """

    molecule: str = Field(
        ...,
        description="The canonical isomeric explicit hydrogen mapped smiles which can be used to build an off molecule.",
    )
    task_id: str = Field(
        ...,
        description="An id given to the parameterization of this molecule  to separate when multiple molecules are to be parameterized separately.",
    )
    initial_forcefield: str = Field(
        ..., description="The initial Forcefield that should then be optimized"
    )
    workflow: Optional[OptimizationSchema] = Field(
        None,
        description="The Optimization schema which specifics the targets that are to be optimized and the run time options to be used during the optimization.",
    )

    @property
    def off_molecule(self) -> off.Molecule:
        """
        Get the openff molecule representation of the input target molecule.
        """
        return off.Molecule.from_mapped_smiles(self.molecule)

    @property
    def n_targets(self) -> int:
        """
        Calculate the number of targets to be fit for this molecule.
        """

        return len(self.workflow.targets)

    @property
    def task_hashes(self) -> List[str]:
        """
        Compute the task hashes for this molecule.
        """
        task_hash = set()

        for target in self.workflow.targets:
            for entry in target.entries:
                task_hash.add(entry.get_hash())
        return list(task_hash)

    def __eq__(self, other: "MoleculeSchema") -> bool:
        """
        Check if two molecule tasks are the same by comparing the task hashes that required inorder to fit the data.
        """
        return self.task_hashes == other.task_hashes

    @property
    def n_tasks(self) -> int:
        """
        Calculate the number of unique tasks to be computed to fit this molecule.
        """
        return len(self.task_hashes)

    def update_with_results(
        self,
        results: List[
            Union[
                BasicCollectionResult,
                OptimizationCollectionResult,
                TorsionDriveCollectionResult,
            ]
        ],
    ) -> None:
        """
        Take a list of result and pass them to the entries to find valid reference data.
        """

        self.workflow.update_with_results(results)

    # def get_next_optimization_stage(self) -> Optional[OptimizationSchema]:
    #     """
    #     Return the next stage in the workflow order which is to be optimized. If no states left returns None to signal it is complete.
    #
    #     Note:
    #         The stage may have an error state.
    #     """
    #     for stage in self.workflow:
    #         if stage.status != Status.Complete:
    #             return stage
    #     return None

    def update_optimization_stage(self, stage: OptimizationSchema) -> None:
        """
        Update the optimization stage with a completed optimization stage.

        Parameters:
            stage: The optimization stage which should be updated into the molecule schema

        Raises:
            WorkflowUpdateError: If no workflow stage in the schema matches the stage supplied.
        """
        if self.workflow.job_id == stage.job_id:
            self.workflow = stage
        else:
            raise WorkflowUpdateError(
                f"No workflow stage matches the job id {stage.job_id}."
            )

    def get_task_map(self) -> Dict[str, List[Task]]:
        """
        Generate a hash map for all of the current tasks to be executed to fit this molecule.
        """
        hash_map = dict()

        workflow_hash = self.workflow.get_task_map()
        for key, tasks in workflow_hash.items():
            hash_map.setdefault(key, []).extend(tasks)

        return hash_map

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
        from chemper.graphs.single_graph import SingleGraph

        from openff.bespokefit.forcefield_tools import ForceFieldEditor

        # check that all optimizations are finished
        if self.workflow.status != Status.Complete:
            raise OptimizerError(
                f"The molecule has not completed all optimization stages which are required to generate the final forcefield."
            )

        # get all of the target smirks
        target_smirks = self.workflow.target_smirks
        # build the parent molecule
        parent_molecule = self.off_molecule

        if drop_out_value is not None:
            # loop over all of the target smirks and drop and torsion k values lower than the drop out
            for smirk in target_smirks:
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
        if self.workflow.extra_parameters:
            fitting_ff.add_smirks(
                smirks=self.workflow.extra_parameters, parameterize=False
            )
        fitting_ff.add_smirks(smirks=target_smirks, parameterize=False)

        if generate_bespoke_terms:
            bespoke_smirks = []
            # get a list of unique fragments and all of the torsions that have been targeted
            for target in self.workflow.targets:
                for entry in target.entries:
                    entry_mol = entry.graph_molecule
                    # check if the smirks are from a fragment
                    fragmented = entry.fragment
                    if not fragmented:
                        # the molecule was not fragmented and already has full bespoke parameters
                        bespoke_smirks.extend(entry.target_smirks)

                    else:
                        # get all of the torsions to be hit by this smirk
                        labels = fitting_ff.label_molecule(molecule=entry_mol)[
                            "ProperTorsions"
                        ]
                        fragment_parent_mapping = entry.fragment_parent_mapping
                        for smirk in entry.target_smirks:
                            for atoms in smirk.atoms:
                                off_smirk = labels[atoms]
                                parent_torsion = [
                                    fragment_parent_mapping[i] for i in atoms
                                ]
                                bespoke_smirk_str = SingleGraph(
                                    mol=parent_molecule.to_rdkit(),
                                    smirks_atoms=parent_torsion,
                                    layers="all",
                                ).as_smirks(compress=False)
                                new_term = TorsionSmirks(smirks=bespoke_smirk_str)
                                new_term.update_parameters(off_smirk=off_smirk)
                                bespoke_smirks.append(new_term)

            # make a new ff object with the new terms
            bespoke_ff = ForceFieldEditor(forcefield_name=self.initial_forcefield)
            bespoke_ff.add_smirks(smirks=bespoke_smirks, parameterize=False)
            return bespoke_ff.forcefield

        else:
            return fitting_ff.forcefield


class FittingSchema(SchemaBase):
    """
    This is the main fitting schema which can be consumed by bespokefit in order to be executed.
    """

    client: str = Field(
        "snowflake",
        description="The type of QCArchive server that will be used, snowflake/snowflake_notebook is a temperary local server that spins up temp compute but can connect to a static server.",
    )
    torsiondrive_dataset_name: str = Field(
        "Bespokefit torsiondrives",
        description="The name given to torsiondrive datasets generated for bespoke fitting",
    )
    optimization_dataset_name: str = Field(
        "Bespokefit optimizations",
        description="The name given to optimization datasets generated for bespoke fitting",
    )
    singlepoint_dataset_name: str = Field(
        "Bespokefit single points",
        description="The common name given to basic datasets needed for bespoke fitting, the driver is appened to the name",
    )
    optimizer_settings: Dict[str, Dict[str, Any]] = Field(
        dict(),
        description="A dictionary containing all run time settings for each optimizaer in the workflow so that they can be rebuilt when optimization tasks are generated.",
    )
    target_settings: Dict[str, Dict[str, Any]] = Field(
        dict(),
        description="A dictonary containing all of the run time settings for each of the targets in the pipeline, they will be used to build each target.",
    )
    tasks: List[MoleculeSchema] = Field(
        [],
        description="The list of molecule schema which represent the individual tasks to be carried out in the fitting procedure.",
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

    def add_molecule_schema(self, molecule_schema: MoleculeSchema) -> None:
        """
        Add a complete molecule schema to the fitting schema.
        """
        # we have to make sure that the optimizer has also been added to the schema.
        assert molecule_schema.workflow.optimizer_name.lower() in self.optimizer_names
        self.tasks.append(molecule_schema)

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
        results: List[
            Union[
                BasicCollectionResult,
                OptimizationCollectionResult,
                TorsionDriveCollectionResult,
            ]
        ],
    ) -> None:
        """
        Take a list of results and try to apply them to each of the molecules in the fitting schema.
        """

        if not isinstance(results, list):
            results = [
                results,
            ]

        for task in self.tasks:
            task.update_with_results(results)

    def generate_qcsubmit_datasets(
        self,
    ) -> List[Union[BasicDataset, OptimizationDataset, TorsiondriveDataset]]:
        """
        Generate a set of qcsubmit datasets containing all of the tasks required to compute the QM data.

        Note:
            Local custom tasks not possible in QCArchive are not included and will be ran when the fitting queue is started.
            Hessian datasets can not be produced until the initial optimization is complete
            The task hash will also be embedded into the entry to make updating the results faster.
        """

        return schema_to_datasets(
            self.tasks,
            singlepoint_name=self.singlepoint_dataset_name,
            optimization_name=self.optimization_dataset_name,
            torsiondrive_name=self.torsiondrive_dataset_name,
        )

    @property
    def molecules(self) -> List[off.Molecule]:
        """
        Return an openforcefield representation of each of the target molecules in the fitting schema.
        """
        return [task.off_molecule for task in self.tasks]

    @property
    def entry_molecules(self) -> List[off.Molecule]:
        """
        Generate a list of unique molecules which we have collection tasks for these are not always the same as the target molecules due to fragmentation.
        """
        unique_molecules = set()
        for task in self.tasks:
            for target in task.workflow.targets:
                for entry in target.entries:
                    unique_molecules.add(entry.initial_molecule)

        return list(unique_molecules)
