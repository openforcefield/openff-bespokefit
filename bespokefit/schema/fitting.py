import hashlib
from typing import Any, Dict, List, Optional, Union

import numpy as np
from openforcefield import topology as off
from openforcefield.typing.engines.smirnoff import ForceField
from pydantic import validator
from qcelemental.models.types import Array
from simtk import unit

from bespokefit.collection_workflows import CollectionMethod, Precedence, WorkflowStage
from qcsubmit.common_structures import QCSpec
from qcsubmit.datasets import BasicDataset, OptimizationDataset, TorsiondriveDataset
from qcsubmit.results import (
    BasicCollectionResult,
    BasicResult,
    OptimizationCollectionResult,
    OptimizationEntryResult,
    SingleResult,
    TorsionDriveCollectionResult,
    TorsionDriveResult,
)
from qcsubmit.validators import cmiles_validator

from ..common_structures import Status, Task
from ..exceptions import DihedralSelectionError, OptimizerError, WorkflowUpdateError
from ..forcefield_tools import ForceFieldEditor
from ..utils import schema_to_datasets
from .schema import SchemaBase
from .smirks import AngleSmirks, AtomSmirks, BondSmirks, SmirksSchema, TorsionSmirks


class FittingEntry(SchemaBase):
    """
    This is the fitting schema which has instructions on how to collect the reference data and fit the parameters for a molecule.
    """

    name: str
    attributes: Dict[str, str]
    collection_workflow: List[WorkflowStage] = []
    target_smirks: List[Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]] = []
    qc_spec: QCSpec = QCSpec()
    provenance: Dict[str, Any] = {}
    extras: Dict[str, Any] = {}
    input_conformers: List[Array[np.ndarray]] = []
    _validate_attributes = validator("attributes", allow_reuse=True)(cmiles_validator)

    @validator("extras")
    def _validate_extras(cls, extras: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dihedrals are stored in the extras field so make sure they are formatted correctly.
        """
        dihedrals = extras.get("dihedrals", None)
        if dihedrals is not None:
            # make sure we have a list of lists/tuples
            if len(dihedrals) == 4:
                # single list
                extras["dihedrals"] = [
                    dihedrals,
                ]
                return extras
            elif len(dihedrals) <= 2:
                return extras
            else:
                raise DihedralSelectionError(
                    f"A maximum of a 2D dihedral scan is supported but a scan of length {len(dihedrals)} was given."
                )
        return extras

    @property
    def initial_molecule(self) -> off.Molecule:
        """
        Create an openFF molecule representation for the FittingSchema with the input geometries.
        """
        off_mol = off.Molecule.from_mapped_smiles(
            self.attributes["canonical_isomeric_explicit_hydrogen_mapped_smiles"]
        )
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
                    for parallel_stage in self.collection_workflow[i:]:
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
        inchi = self.initial_molecule.to_inchi(
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
            dihedral = str(self.extras["dihedrals"])
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

    @property
    def reference_data(self) -> List[SingleResult]:
        """
        Return the final result of the collection workflow.
        """
        return self.collection_workflow[-1].result

    @property
    def ready_for_fitting(self) -> bool:
        """
        A self validation method to make sure the molecule is ready for fitting.

        Returns:
            `True` if all information is present else `False`.
        """
        # check the last stage is ready for fitting
        stage = self.collection_workflow[-1]
        if stage.status == Status.Complete and stage.result is not None:
            return True

    def update_with_results(
        self, results: Union[BasicResult, TorsionDriveResult, OptimizationEntryResult]
    ) -> None:
        """
        This will update the fitting entry with results collected with qcsubmit, the type of data accepted depends here on the collection method specified.

        Note:
            - torsiondrive1d/2d will accept TorsionDriveResults and OptimizationEntryResult if it is constrained
            - singlepoints will accept any input type.
        """
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
                        # work out if the result and schema target the same dihedral
                        dihedral = set(self.extras["dihedrals"][0][1:3])
                        # now map the result dihedral back
                        target_dihedral = set(
                            [atom_map[i] for i in results.dihedrals[0][1:3]]
                        )
                        if not target_dihedral.difference(dihedral):
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
                            RuntimeError(
                                f"Molecules are the same but do not target the same dihedral."
                            )
                    else:
                        raise RuntimeError(
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
            new_conformer[i] = result.molecule.geometry[mapping[i]]
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

    target_name: str
    provenance: Dict[str, Any]
    entries: List[FittingEntry] = []

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
        Collect all of the new target smirks from the entries for this target.
        """
        target_smirks = []
        for entry in self.entries:
            target_smirks.extend(entry.target_smirks)

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
                            result.program == entry.qc_spec.program
                            and result.method == entry.qc_spec.method
                            and result.basis == entry.qc_spec.basis
                        ):
                            try:
                                entry.update_with_results(td_result)
                            except RuntimeError:
                                continue
                        else:
                            continue
            else:
                raise NotImplementedError()


class WorkflowSchema(SchemaBase):
    """
    This class collects together an optimizer with its targets and the entries.
    """

    optimizer_name: str
    job_id: str
    targets: List[TargetSchema] = []
    status: Status = Status.Prepared
    extra_parameters: List[
        Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]
    ] = []

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
    ) -> List[Union[BondSmirks, AngleSmirks, TorsionSmirks, AtomSmirks]]:
        """
        Get all of the smirks targeted by the optimization targets which are part of this workflow.
        """
        target_smirks = [
            smirk for target in self.targets for smirk in target.get_target_smirks()
        ]
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

        # get all of the new target smirks
        target_smirks = [
            smirk for target in self.targets for smirk in target.get_target_smirks()
        ]
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

    molecule: str  # the mapped smiles
    initial_forcefield: str
    workflow: List[WorkflowSchema] = []

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

        return sum([len(workflow.targets) for workflow in self.workflow])

    @property
    def task_hashes(self) -> List[str]:
        """
        Compute the task hashes for this molecule.
        """
        task_hash = set()
        for stage in self.workflow:
            for target in stage.targets:
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

        for workflow_stage in self.workflow:
            workflow_stage.update_with_results(results)

    def get_next_optimization_stage(self) -> Optional[WorkflowSchema]:
        """
        Return the next stage in the workflow order which is to be optimized. If no states left returns None to signal it is complete.

        Note:
            The stage may have an error state.
        """
        for stage in self.workflow:
            if stage.status != Status.Complete:
                return stage
        return None

    def update_optimization_stage(self, stage: WorkflowSchema) -> None:
        """
        Update an optimization stage with a completed optimization stage.

        Parameters:
            stage: The optimization stage which should be updated into the molecule schema

        Raises:
            WorkflowUpdateError: If no workflow stage in the schema matches the stage supplied.
        """
        for i, workflow in enumerate(self.workflow):
            if workflow.job_id == stage.job_id:
                self.workflow[i] = stage
                break
        else:
            raise WorkflowUpdateError(
                f"No workflow stage matches the job id {stage.job_id}."
            )

    def get_task_map(self) -> Dict[str, List[Task]]:
        """
        Generate a hash map for all of the current tasks to be executed to fit this molecule.
        """
        hash_map = dict()
        for workflow in self.workflow:
            workflow_hash = workflow.get_task_map()
            for key, tasks in workflow_hash.items():
                hash_map.setdefault(key, []).extend(tasks)

        return hash_map


class FittingSchema(SchemaBase):
    """
    This is the main fitting schema which can be consumed by bespokefit in order to be executed.
    """

    client: str
    torsiondrive_dataset_name: str = "Bespokefit torsiondrives"
    optimization_dataset_name: str = "Bespokefit optimizations"
    singlepoint_dataset_name: str = "Bespokefit single points"
    optimizer_settings: Dict[str, Dict[str, Any]] = {}
    molecules: List[MoleculeSchema] = []

    def add_optimizer(self, optimizer: "Optimizer") -> None:
        """
        Add a valid optimizer to the fitting schema.
        """
        from ..optimizers import list_optimizers

        if optimizer.optimizer_name.lower() in list_optimizers():
            if optimizer.optimizer_name not in self.optimizer_settings:
                self.optimizer_settings[
                    optimizer.optimizer_name.lower()
                ] = optimizer.dict(exclude={"optimization_targets"})
        else:
            raise KeyError(
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
        for stage in molecule_schema.workflow:
            assert stage.optimizer_name.lower() in self.optimizer_names
        self.molecules.append(molecule_schema)

    def export_schema(self, file_name: str) -> None:
        """
        Export the fitting schema to file.
        """
        file_type = file_name.split(".")[-1]
        if file_type.lower() == "json":
            with open(file_name, "w") as output:
                output.write(self.json(indent=2))
        else:
            raise RuntimeError(
                f"The given file type: {file_type} is not supported please used json."
            )

    @property
    def n_molecules(self) -> int:
        """
        Calculate the number of initial molecules to be optimized.
        """

        return len(self.molecules)

    @property
    def task_hashes(self) -> List[str]:
        """
        Get all of the unique task hashes.
        """
        tasks = set()
        for molecule in self.molecules:
            tasks.update(molecule.task_hashes)
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

        for molecule in self.molecules:
            molecule.update_with_results(results)

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
            self.molecules,
            singlepoint_name=self.singlepoint_dataset_name,
            optimization_name=self.optimization_dataset_name,
            torsiondrive_name=self.torsiondrive_dataset_name,
        )
