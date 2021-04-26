"""
This is the main bespokefit workflow factory which is executed and builds the bespoke
workflows.
"""
import os
from typing import Dict, List, Optional, Tuple, Union

from openff.qcsubmit.common_structures import MoleculeAttributes, ResultsConfig
from openff.qcsubmit.datasets import ComponentResult
from openff.qcsubmit.results import (
    BasicCollectionResult,
    BasicResult,
    OptimizationCollectionResult,
    OptimizationResult,
    TorsionDriveCollectionResult,
    TorsionDriveResult,
)
from openff.qcsubmit.serializers import serialize
from openff.toolkit.topology import Molecule
from openff.toolkit.typing.engines.smirnoff import get_available_force_fields
from pydantic import Field, validator

from openff.bespokefit.bespoke.smirks import SmirksGenerator
from openff.bespokefit.exceptions import (
    ForceFieldError,
    FragmenterError,
    OptimizerError,
    TargetNotSetError,
)
from openff.bespokefit.fragmentation import WBOFragmenter
from openff.bespokefit.optimizers import get_optimizer, list_optimizers
from openff.bespokefit.schema.bespoke import MoleculeSchema
from openff.bespokefit.schema.bespoke.tasks import (
    HessianTask,
    OptimizationTask,
    TorsionTask,
)
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.optimizers import ForceBalanceSchema, OptimizerSchema
from openff.bespokefit.schema.smirnoff import (
    ProperTorsionSettings,
    SmirksParameterSettings,
    SmirksType,
)
from openff.bespokefit.schema.targets import (
    BespokeQCData,
    TargetSchema,
    TorsionProfileTargetSchema,
)
from openff.bespokefit.utilities import get_molecule_cmiles
from openff.bespokefit.utilities.pydantic import ClassBase


class BespokeWorkflowFactory(ClassBase):
    """
    The bespokefit workflow factory which is a template of the settings that will be
    used to generate the specific fitting schema for each molecule.
    """

    initial_force_field: str = Field(
        "openff_unconstrained-1.3.0.offxml",
        description="The name of the unconstrained force field to use as a starting "
        "point for optimization. The force field must be conda installed.",
    )

    optimizer: Union[str, OptimizerSchema] = Field(
        ForceBalanceSchema(),
        description="The optimizer that should be used with the targets already set.",
    )

    target_templates: List[TargetSchema] = Field(
        [TorsionProfileTargetSchema()],
        description="Templates for the fitting targets to use as part of the "
        "optimization. The ``reference_data`` attribute of each schema will be "
        "automatically populated by this factory.",
    )

    parameter_settings: List[SmirksParameterSettings] = Field(
        [
            ProperTorsionSettings(),
        ],
        description="The settings which describe how types of parameters, e.g. the "
        "force constant of a bond parameter, should be restrained during the "
        "optimisation such as through the inclusion of harmonic priors.",
    )
    target_smirks: List[SmirksType] = Field(
        [
            SmirksType.ProperTorsions,
        ],
        description="The list of parameters the new smirks patterns should be made for.",
    )

    expand_torsion_terms: bool = Field(
        True,
        description="If the optimization should first expand the number of k values "
        "that should be fit for each torsion beyond what is in the initial force field.",
    )
    generate_bespoke_terms: bool = Field(
        True,
        description="If the optimized smirks should be bespoke to the target molecules.",
    )

    fragmentation_engine: Optional[Union[WBOFragmenter]] = Field(
        WBOFragmenter(),
        description="The Fragment engine that should be used to fragment the molecule, "
        "note that if None is provided the molecules will not be fragmented. By default "
        "we use the WBO fragmenter by the Open Force Field Consortium.",
    )

    @validator("initial_force_field")
    def _check_force_field(cls, force_field: str) -> str:
        """Check that the force field is available via the toolkit.
        TODO add support for local force fields and store the string
        """

        openff_force_fields = get_available_force_fields()

        if force_field not in openff_force_fields:
            raise ForceFieldError(
                f"The force field {force_field} is not installed please chose a "
                f"force field from the following {openff_force_fields}"
            )
        else:
            return force_field

    @validator("optimizer")
    def _check_optimizer(cls, optimizer: Union[str, OptimizerSchema]):
        """
        Set the optimizer settings to be used.

        Parameters
        ----------
        optimizer: Union[str, BaseOptimizer]
            The optimizer that should be added to the workflow, targets should also be
            added before creating the fitting schema.
        """

        if isinstance(optimizer, str):
            # we can check for the optimizer and attach it
            return get_optimizer(optimizer.lower())()

        if optimizer.type.lower() not in list_optimizers():

            raise OptimizerError(
                f"The requested optimizer {optimizer.type} was not registered "
                f"with bespokefit."
            )

        return optimizer

    # @classmethod
    # def parse_file(
    #     cls,
    #     path,
    #     *,
    #     content_type: str = None,
    #     encoding: str = "utf8",
    #     proto=None,
    #     allow_pickle: bool = False,
    # ) -> "BespokeWorkflowFactory":
    #     """
    #     Here we overwrite the parse function to work with json and yaml and to unpack
    #     the workflow.
    #     """
    #     data = deserialize(file_name=path)
    #     optimizer = data.pop("optimizer")
    #     fragmentation_engine = data.pop("fragmentation_engine")
    #     if fragmentation_engine is not None:
    #         fragmenter = get_fragmentation_engine(**fragmentation_engine)
    #     else:
    #         fragmenter = None
    #     workflow = cls.parse_obj(data)
    #     # set the fragmentation engine
    #     workflow.fragmentation_engine = fragmenter
    #     # now we need to re init the optimizer and the targets
    #     opt_targets = optimizer.pop("optimization_targets")
    #     opt_engine = get_optimizer(**optimizer)
    #     opt_engine.clear_optimization_targets()
    #     for target in opt_targets:
    #         opt_engine.set_optimization_target(target=target["name"], **target)
    #     workflow.optimizer = opt_engine
    #
    #     return workflow

    def export_workflow(self, file_name: str) -> None:
        """
        Export the workflow to yaml or json file.

        Parameters
        ----------
        file_name: str
            The name of the file the workflow should be exported to, the type is
            determined from the name.
        """

        serialize(serializable=self.dict(), file_name=file_name)

    def _pre_run_check(self) -> None:
        """
        Check that all required settings are declared before running.
        """

        # now check we have targets in each optimizer
        if len(self.target_templates) == 0:
            raise OptimizerError(
                "There are no optimization targets in the optimization workflow."
            )
        elif not self.fragmentation_engine:
            raise FragmenterError(
                "There is no fragmentation engine registered for the workflow."
            )
        elif len(self.parameter_settings) == 0:
            raise TargetNotSetError(
                "There are no parameter settings specified which will mean that the "
                "optimiser has no parameters to optimize."
            )
        elif len(self.target_smirks) == 0:
            raise TargetNotSetError(
                "No forcefield groups have been supplied, which means no smirks were "
                "selected to be optimized."
            )
        else:
            return

    @classmethod
    def _generate_fitting_task(
        cls,
        target_schema: TargetSchema,
        molecule: Molecule,
        fragment: bool,
        attributes: MoleculeAttributes,
        fragment_parent_mapping: Optional[Dict[int, int]] = None,
        dihedrals: Optional[List[Tuple[int, int, int, int]]] = None,
    ) -> Union[TorsionTask, OptimizationTask, HessianTask]:
        """
        For the given collection workflow generate a task schema for the input molecule.
        """
        if molecule.n_conformers < target_schema.reference_data.target_conformers:

            molecule.generate_conformers(
                n_conformers=target_schema.reference_data.target_conformers,
                clear_existing=False,
            )

        collection_workflow = target_schema.bespoke_task_type()

        # build a dict of the data
        data = dict(
            name=collection_workflow,
            attributes=attributes,
            provenance={},
            fragment=fragment,
            fragment_parent_mapping=fragment_parent_mapping,
            molecule=molecule,
            dihedrals=dihedrals,
        )

        if collection_workflow == "torsion1d":
            task = TorsionTask(**data)
        elif collection_workflow == "optimization":
            task = OptimizationTask(**data)
        elif collection_workflow == "hessian":
            task = HessianTask(**data)
        else:
            raise NotImplementedError(
                f"The collection workflow `{collection_workflow}` is not supported."
            )

        return task

    @classmethod
    def _deduplicated_list(
        cls, molecules: Union[Molecule, List[Molecule], str]
    ) -> ComponentResult:
        """
        Create a deduplicated list of molecules based on the input type.
        """

        input_file, molecule, input_directory = None, None, None

        if isinstance(molecules, str):

            # this is an input file or folder
            if os.path.isfile(molecules):
                input_file = molecules
            else:
                input_directory = molecules

        elif isinstance(molecules, Molecule):
            molecule = [molecules]
        else:
            molecule = molecules

        return ComponentResult(
            component_name="default",
            component_provenance={},
            component_description={},
            molecules=molecule,
            input_file=input_file,
            input_directory=input_directory,
        )

    def optimization_schemas_from_molecules(
        self,
        molecules: Union[Molecule, List[Molecule]],
        processors: Optional[int] = None,
    ) -> List[BespokeOptimizationSchema]:
        """This is the main function of the workflow which takes the general fitting
        meta-template and generates a specific one for the set of molecules that are
        passed.

        #TODO: Expand to accept the QCSubmit results datasets directly to create the
               fitting schema and fill the tasks.
        #TODO how do we support dihedral tagging?

        Parameters
        ----------
        molecules:
            The molecule or list of molecules which should be processed by the schema to
            generate the fitting schema.
        processors:
            The number of processors that should be used when building the workflow,
            this helps with fragmentation which can be quite slow for large numbers of
            molecules.
        """

        from multiprocessing.pool import Pool

        import tqdm

        # make sure all required variables have been declared
        self._pre_run_check()

        # create a deduplicated list of molecules first.
        deduplicated_molecules = self._deduplicated_list(molecules=molecules)

        optimization_schemas = []

        # now set up a process pool to do fragmentation and create the fitting schema
        # while retaining the original fitting order
        if processors is None or processors > 1:
            with Pool() as pool:

                schema_list = [
                    pool.apply_async(
                        self.optimization_schema_from_molecule, (molecule, i)
                    )
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
                    optimization_schemas.append(schema)
        else:
            # run with 1 processor
            for i, molecule in tqdm.tqdm(
                enumerate(deduplicated_molecules.molecules),
                total=deduplicated_molecules.n_molecules,
                ncols=80,
                desc="Building Fitting Schema",
            ):

                schema = self.optimization_schema_from_molecule(
                    molecule=molecule, index=i
                )
                optimization_schemas.append(schema)

        return optimization_schemas

    def optimization_schema_from_molecule(
        self, molecule: Molecule, index: int = 0
    ) -> BespokeOptimizationSchema:
        """Build an optimization schema from an input molecule this involves
        fragmentation.
        """

        # make sure all required variables have been declared
        self._pre_run_check()

        # Fragment the molecule.
        fragment_data = self.fragmentation_engine.fragment(molecule=molecule)

        attributes = get_molecule_cmiles(molecule=molecule)
        molecule_schema = MoleculeSchema(
            attributes=attributes,
            task_id=f"bespoke_task_{index}",
            fragment_data=[],
            fragmentation_engine=self.fragmentation_engine.dict(),
        )

        # Build the optimization schema
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
        opt_schema.targets = []

        for target_template in self.target_templates:

            target_schema = target_template.copy(deep=True)

            if target_schema.reference_data is None:
                target_schema.reference_data = BespokeQCData()

            # Clear the task list in case the user tried to provide some.
            target_schema.reference_data.tasks = []

            for task_index, fragment in enumerate(molecule_schema.fragment_data):

                task_schema = self._generate_fitting_task(
                    target_schema=target_schema,
                    molecule=fragment.molecule,
                    fragment=True,
                    attributes=fragment.fragment_attributes,
                    fragment_parent_mapping=fragment.fragment_parent_mapping,
                    dihedrals=[fragment.target_dihedral],
                )
                task_schema.name = f"{target_schema.bespoke_task_type()}-{task_index}"
                target_schema.reference_data.tasks.append(task_schema)

            opt_schema.targets.append(target_schema)

        return opt_schema

    def optimization_schemas_from_results(
        self,
        results: Union[
            TorsionDriveCollectionResult,
            OptimizationCollectionResult,
            BasicCollectionResult,
        ],
        combine: bool = False,
        processors: Optional[int] = None,
    ) -> List[BespokeOptimizationSchema]:
        """
        Create a set of optimization schemas (one per molecule) from some results.

        Here input molecules are turned into tasks and results are updated during the
        process.

        If multiple targets are in the workflow the results will be applied to the
        correct target other targets can be updated after by calling update with
        parameters.
        """
        from multiprocessing.pool import Pool

        import tqdm

        # make sure all required variables have been declared
        self._pre_run_check()

        # group the tasks if requested
        all_tasks = self._sort_results(results=results, combine=combine)

        optimization_schemas = []

        # now set up a process pool to do fragmentation and create the fitting schema
        # while retaining the original fitting order
        if processors is None or processors > 1:
            with Pool() as pool:
                schema_list = [
                    pool.apply_async(self._optimization_schema_from_results, task)
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
                    optimization_schemas.append(schema)
        else:
            # run with 1 processor
            for i, task in tqdm.tqdm(
                all_tasks,
                total=len(all_tasks),
                ncols=80,
                desc="Building Fitting Schema",
            ):
                schema = self._optimization_schema_from_results(*task)
                optimization_schemas.append(schema)

        return optimization_schemas

    @classmethod
    def _sort_results(
        cls,
        results: Union[
            TorsionDriveCollectionResult,
            OptimizationCollectionResult,
            BasicCollectionResult,
        ],
        combine: bool = False,
    ) -> List[Tuple[List[ResultsConfig], int]]:
        """Sort the results into a list that can be processed into a fitting schema,
        combining results when requested.
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

    def _optimization_schema_from_results(
        self,
        results: List[Union[TorsionDriveResult, OptimizationResult, BasicResult]],
        index: int,
    ) -> BespokeOptimizationSchema:
        """
        Create an optimization task for a given list of results.

        Notes
        -----
        * This method assumes a result records were generated for the same molecule.
        * The list allows multiple results to be combined from the same molecule which is
          mostly useful for torsion drives.
        """

        molecule_schema = MoleculeSchema(
            attributes=MoleculeAttributes(**results[0].attributes),
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
                central_bonds=[bond],
            )
            all_smirks.extend(new_smirks)

        # finish the optimization schema
        opt_schema.target_molecule = molecule_schema
        opt_schema.target_smirks = all_smirks

        # now loop over the targets and build the reference tasks
        for target_template in self.target_templates:

            target_schema = target_template.copy(deep=True)

            if target_schema.reference_data is None:
                target_schema.reference_data = BespokeQCData()

            tasks = []

            for result in results:

                task_schema = self._generate_fitting_task(
                    target_schema=target_schema,
                    molecule=result.molecule,
                    fragment=False,
                    attributes=MoleculeAttributes(**result.attributes),
                    fragment_parent_mapping=None,
                    dihedrals=getattr(result, "dihedrals", None),
                )
                task_schema.update_with_results(results=result)
                tasks.append(task_schema)

            target_schema.reference_data.tasks = tasks
            opt_schema.targets.append(target_schema)

        return opt_schema

    def _get_smirks_generator(self) -> SmirksGenerator:
        """
        Build a smirks generator from the set of inputs.
        """
        smirks_gen = SmirksGenerator(
            initial_force_field=self.initial_force_field,
            generate_bespoke_terms=self.generate_bespoke_terms,
            expand_torsion_terms=self.expand_torsion_terms,
            target_smirks=self.target_smirks,
        )
        return smirks_gen

    def _build_optimization_schema(
        self, molecule_schema: MoleculeSchema, index: int
    ) -> BespokeOptimizationSchema:
        """
        For a given molecule schema build an optimization schema.
        """
        schema = BespokeOptimizationSchema(
            initial_force_field=self.initial_force_field,
            optimizer=self.optimizer,
            parameter_settings=self.parameter_settings,
            id=f"bespoke_task_{index}",
            target_molecule=molecule_schema,
        )
        return schema
