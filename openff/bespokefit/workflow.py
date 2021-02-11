"""
This is the main bespokefit workflow factory which is executed and builds the bespoke workflows.
"""

from typing import List, Optional, Tuple, Union

from openforcefield import topology as off
from openforcefield.typing.engines.smirnoff import get_available_force_fields
from pydantic import BaseModel, Field, validator

from openff.bespokefit.common_structures import (
    ProperTorsionSettings,
    SmirksSettings,
    SmirksType,
)
from openff.bespokefit.exceptions import (
    ForceFieldError,
    FragmenterError,
    OptimizerError,
    TargetNotSetError,
)
from openff.bespokefit.fragmentation import (
    FragmentEngine,
    WBOFragmenter,
    get_fragmentation_engine,
)
from openff.bespokefit.optimizers import Optimizer, get_optimizer, list_optimizers
from openff.bespokefit.schema import FittingSchema, MoleculeSchema, OptimizationSchema
from openff.bespokefit.smirks import SmirksGenerator
from openff.bespokefit.utils import deduplicated_list
from openff.qcsubmit.results import (
    BasicCollectionResult,
    BasicResult,
    OptimizationCollectionResult,
    OptimizationResult,
    TorsionDriveCollectionResult,
    TorsionDriveResult,
)
from openff.qcsubmit.serializers import deserialize, serialize


class WorkflowFactory(BaseModel):
    """
    The bespokefit workflow factory which is a template of the settings that will be used to generate the specific fitting schema for each molecule.
    """

    initial_forcefield: str = Field(
        "openff_unconstrained-1.3.0.offxml",
        description="The name of the unconstrained forcefield to use as a starting point for optimization. The forcefield must be conda installed.",
    )
    expand_torsion_terms: bool = Field(
        True,
        description="If the optimization should first expand the number of k values that should be fit for each torsion beyond what is in the initial force field.",
    )
    generate_bespoke_terms: bool = Field(
        True,
        description="If the optimized smirks should be bespoke to the target molecules.",
    )
    optimizer: Optional[Optimizer] = Field(
        None,
        description="The optimizer that should be used with the targets already set.",
    )
    fragmentation_engine: Optional[FragmentEngine] = Field(
        WBOFragmenter(),
        description="The Fragment engine that should be used to fragment the molecule, note that if None is "
        "provided the molecules will not be fragmented. By default we use the WBO fragmenter by openforcefield.",
    )
    target_parameters: SmirksSettings = Field(
        [
            ProperTorsionSettings(),
        ],
        description="The set of specific parameters that should be optimmized such as bond length.",
    )
    target_smirks: List[SmirksType] = Field(
        [
            SmirksType.ProperTorsions,
        ],
        description="The list of parameters the new smirks patterns should be made for.",
    )

    class Config:
        validate_assignment = True
        allow_mutation = True
        arbitrary_types_allowed = True

    @validator("initial_forcefield")
    def _check_forcefield(cls, forcefield: str) -> str:
        """
        Check that the forcefield is available via the toolkit.
        TODO add support for local forcefields and store the string
        """
        openff_forcefields = get_available_force_fields()
        if forcefield not in openff_forcefields:
            raise ForceFieldError(
                f"The forcefield {forcefield} is not installed please chose a forcefield from the following {openff_forcefields}"
            )
        else:
            return forcefield

    @classmethod
    def parse_file(
        cls,
        path,
        *,
        content_type: str = None,
        encoding: str = "utf8",
        proto=None,
        allow_pickle: bool = False,
    ) -> "WorkflowFactory":
        """
        Here we overwrite the parse function to work with json and yaml and to unpack the workflow.
        """
        data = deserialize(file_name=path)
        optimizer = data.pop("optimizer")
        fragmentation_engine = data.pop("fragmentation_engine")
        if fragmentation_engine is not None:
            fragmenter = get_fragmentation_engine(**fragmentation_engine)
        else:
            fragmenter = None
        workflow = cls.parse_obj(data)
        # set the fragmentation engine
        workflow.fragmentation_engine = fragmenter
        # now we need to re init the optimizer and the targets
        opt_targets = optimizer.pop("optimization_targets")
        opt_engine = get_optimizer(**optimizer)
        opt_engine.clear_optimization_targets()
        for target in opt_targets:
            opt_engine.set_optimization_target(target=target["name"], **target)
        workflow.optimizer = opt_engine

        return workflow

    def set_optimizer(self, optimizer: Union[str, Optimizer]) -> None:
        """
        Set the optimizer to be used.

        Parameters
        ----------
        optimizer: Union[str, Optimizer]
            The optimizer that should be added to the workflow, targets should also be added before creating the fitting schema.
        """

        if isinstance(optimizer, str):
            # we can check for the optimizer and attach it
            opt_engine = get_optimizer(optimizer.lower())

        else:
            if optimizer.optimizer_name.lower() in list_optimizers():
                opt_engine = optimizer

            else:
                raise OptimizerError(
                    f"The requested optimizer {optimizer} was not registered with bespokefit."
                )

        self.optimizer = opt_engine

    def clear_optimizer(self) -> None:
        """
        Clear out the optimizer and reset the workflow.
        """
        self.optimizer = None

    def export_workflow(self, file_name: str) -> None:
        """
        Export the workflow to yaml or json file.

        Parameters
        ----------
        file_name: str
            The name of the file the workflow should be exported to, the type is determined from the name.
        """

        serialize(serializable=self.dict(), file_name=file_name)

    def _pre_run_check(self) -> None:
        """
        Check that all required settings are declared before running.
        """
        # check we have an optimizer in the pipeline
        if self.optimizer is None:
            raise OptimizerError(
                "No optimizer has been set please set it using `set_optimizer`"
            )
        # now check we have targets in each optimizer
        elif not self.optimizer.optimization_targets:
            raise OptimizerError(
                f"There are no optimization targets for the optimizer {self.optimizer.optimizer_name} in the optimization workflow."
            )
        elif not self.fragmentation_engine:
            raise FragmenterError(
                f"There is no fragmentation engine registered for the workflow."
            )
        elif not self.target_parameters:
            raise TargetNotSetError(
                f"No target parameter was set, this will mean that the optimiser has no parameters to optimize."
            )
        elif not self.target_smirks:
            raise TargetNotSetError(
                f"No forcefield groups have been supplied, which means no smirks were selected to be optimized."
            )
        else:
            return

    def fitting_schema_from_molecules(
        self,
        molecules: Union[off.Molecule, List[off.Molecule]],
        processors: Optional[int] = None,
    ) -> FittingSchema:
        """
        This is the main function of the workflow which takes the general fitting metatemplate and generates a specific
        one for the set of molecules that are passed.

        #TODO Expand to accept the QCSubmit results datasets directly to create the fitting schema and fill the tasks.
        #TODO how do we support dihedral tagging?

        Parameters
        ----------
        molecules: The molecule or list of molecules which should be processed by the schema to generate the fitting schema.
        processors: The number of processors that should be used when building the workflow, this helps with fragmentation
            which can be quite slow for large numbers of molecules.
        """
        # make sure all required variables have been declared
        self._pre_run_check()

        from multiprocessing.pool import Pool

        import tqdm

        # create a deduplicated list of molecules first.
        deduplicated_molecules = deduplicated_list(molecules=molecules)

        fitting_schema = FittingSchema()
        # add the settings for the optimizer and its targets
        fitting_schema.add_optimizer(self.optimizer)

        # now set up a process pool to do fragmentation and create the fitting schema while retaining
        # the original fitting order
        if processors is None or processors > 1:
            with Pool() as pool:
                schema_list = [
                    pool.apply_async(self._task_from_molecule, (molecule, i))
                    for i, molecule in enumerate(deduplicated_molecules.molecules)
                ]
                # loop over the list and add the tasks fo the main fitting schema
                for task in tqdm.tqdm(
                    schema_list,
                    total=len(schema_list),
                    ncols=80,
                    desc="Building Fitting Schema ",
                ):
                    schema = task.get()
                    fitting_schema.add_optimization_task(schema)
        else:
            # run with 1 processor
            for i, molecule in tqdm.tqdm(
                enumerate(deduplicated_molecules.molecules),
                total=deduplicated_molecules.n_molecules,
                ncols=80,
                desc="Building Fitting Schema",
            ):

                schema = self._task_from_molecule(molecule=molecule, index=i)
                fitting_schema.add_optimization_task(schema)

        return fitting_schema

    def _task_from_molecule(
        self, molecule: off.Molecule, index: int
    ) -> OptimizationSchema:
        """
        Build an optimization schema from an input molecule this involves fragmentation.
        """
        from openff.bespokefit.utils import get_molecule_cmiles

        fragment_data = self.fragmentation_engine.fragment(molecule=molecule)
        attributes = get_molecule_cmiles(molecule=molecule)
        molecule_schema = MoleculeSchema(
            attributes=attributes,
            task_id=f"bespoke_task_{index}",
            fragment_data=[],
            fragmentation_engine=self.fragmentation_engine.dict(),
        )
        # build the optimization schema
        opt_schema = self._build_optimization_schema(
            molecule_schema=molecule_schema, index=index
        )
        smirks_gen = self._get_smirks_generator()
        all_smirks = []
        for fragment in fragment_data:
            # get the smirks and build the fragment schema
            fragment_schema = fragment.fragment_schema()
            new_smirks = smirks_gen.generate_smirks(
                molecule=fragment_schema.molecule,
                central_bonds=[
                    fragment.fragment_torsion,
                ],
            )
            all_smirks.extend(new_smirks)
            molecule_schema.add_fragment(fragment=fragment_schema)

        # finish the optimization schema
        opt_schema.target_molecule = molecule_schema
        opt_schema.target_smirks = all_smirks

        # now loop over the targets and build the reference tasks
        for target in self.optimizer.optimization_targets:
            target_schema = target.generate_target_schema()
            for fragment in molecule_schema.fragment_data:
                task_schema = target.generate_fitting_task(
                    molecule=fragment.molecule,
                    fragment=True,
                    attributes=fragment.fragment_attributes,
                    fragment_parent_mapping=fragment.fragment_parent_mapping,
                    dihedrals=[
                        fragment.target_dihedral,
                    ],
                )
                target_schema.add_fitting_task(task=task_schema)
            opt_schema.add_target(target=target_schema)

        return opt_schema

    def fitting_schema_from_results(
        self,
        results: Union[
            TorsionDriveCollectionResult,
            OptimizationCollectionResult,
            BasicCollectionResult,
        ],
        combine: bool = False,
        processors: Optional[int] = None,
    ) -> FittingSchema:
        """
        Create a fitting schema from some results, here input molecules are turned into tasks and results are updated during the process.
        If multiple targets are in the workflow the results will be applied to the correct target other targets can be updated after by calling update with parameters.
        """
        # make sure all required variables have been declared
        self._pre_run_check()

        from multiprocessing.pool import Pool

        import tqdm

        # group the tasks if requested
        all_tasks = self._sort_results(results=results, combine=combine)

        fitting_schema = FittingSchema()
        # add the settings for the optimizer and its targets
        fitting_schema.add_optimizer(self.optimizer)

        # now set up a process pool to do fragmentation and create the fitting schema while retaining
        # the original fitting order
        if processors is None or processors > 1:
            with Pool() as pool:
                schema_list = [
                    pool.apply_async(self._task_from_results, task)
                    for task in all_tasks
                ]
                # loop over the list and add the tasks fo the main fitting schema
                for task in tqdm.tqdm(
                    schema_list,
                    total=len(schema_list),
                    ncols=80,
                    desc="Building Fitting Schema ",
                ):
                    schema = task.get()
                    fitting_schema.add_optimization_task(schema)
        else:
            # run with 1 processor
            for i, task in tqdm.tqdm(
                all_tasks,
                total=len(all_tasks),
                ncols=80,
                desc="Building Fitting Schema",
            ):
                schema = self._task_from_results(*task)
                fitting_schema.add_optimization_task(schema)

        return fitting_schema

    def _sort_results(
        self,
        results: Union[
            TorsionDriveCollectionResult,
            OptimizationCollectionResult,
            BasicCollectionResult,
        ],
        combine: bool = False,
    ) -> List[Tuple[List, int]]:
        """
        Sort the results into a list that can be processed into a fitting schema, combining results when requested.
        """
        all_tasks = []
        if combine:
            # loop over the results and combine multiple results for the same molecule
            # this only effects multiple torsion drives
            dedup_tasks = {}
            for result in results.collection.values():
                # get the unique inchi key
                inchi_key = result.molecule.to_inchikey(fixed_hydrogens=True)
                dedup_tasks.setdefault(inchi_key, []).append(result)
            # now make a list of tasks
            for i, tasks in enumerate(dedup_tasks.values()):
                all_tasks.append((tasks, i))
        else:
            for i, task in enumerate(results.collection.values()):
                all_tasks.append(
                    (
                        [
                            task,
                        ],
                        i,
                    )
                )

        return all_tasks

    def _task_from_results(
        self,
        results: List[Union[TorsionDriveResult, OptimizationResult, BasicResult]],
        index: int,
    ) -> OptimizationSchema:
        """
        Create an optimization task for a given list of results, the list allows multiple results to be combined from the same molecule
        this is must useful for torsiondrives.
        """
        molecule_schema = MoleculeSchema(
            attributes=results[0].attributes,
            task_id=results[0].molecule.to_smiles(),
            fragment_data=[],
            fragmentation_engine=None,
        )
        opt_schema = self._build_optimization_schema(
            molecule_schema=molecule_schema, index=index
        )
        smirks_gen = self._get_smirks_generator()
        all_smirks = []
        for result in results:
            dihedrals = getattr(result, "dihedrals", None)
            if dihedrals is not None:
                bond = tuple([dihedrals[0][1], dihedrals[0][2]])
            else:
                bond = None
            new_smirks = smirks_gen.generate_smirks(
                molecule=result.molecule,
                central_bonds=[
                    bond,
                ],
            )
            all_smirks.extend(new_smirks)

        # finish the optimization schema
        opt_schema.target_molecule = molecule_schema
        opt_schema.target_smirks = all_smirks

        # now loop over the targets and build the reference tasks
        for target in self.optimizer.optimization_targets:
            target_schema = target.generate_target_schema()
            for result in results:
                task_schema = target.generate_fitting_task(
                    molecule=result.molecule,
                    fragment=False,
                    attributes=result.attributes,
                    fragment_parent_mapping=None,
                    dihedrals=getattr(result, "dihedrals", None),
                )
                task_schema.update_with_results(results=result)
                target_schema.add_fitting_task(task=task_schema)
            opt_schema.add_target(target=target_schema)

        return opt_schema

    def _get_smirks_generator(self) -> SmirksGenerator:
        """
        Build a smirks generator from the set of inputs.
        """
        smirks_gen = SmirksGenerator(
            initial_forcefield=self.initial_forcefield,
            generate_bespoke_terms=self.generate_bespoke_terms,
            expand_torsion_terms=self.expand_torsion_terms,
            target_smirks=self.target_smirks,
        )
        return smirks_gen

    def _build_optimization_schema(
        self, molecule_schema: MoleculeSchema, index: int
    ) -> OptimizationSchema:
        """
        For a given molecule schema build an optimization schema.
        """
        schema = OptimizationSchema(
            initial_forcefield=self.initial_forcefield,
            optimizer_name=self.optimizer.optimizer_name,
            settings=self.optimizer.dict(exclude={"optimization_targets"}),
            target_parameters=self.target_parameters,
            job_id=f"bespoke_task_{index}",
            target_molecule=molecule_schema,
        )
        return schema
