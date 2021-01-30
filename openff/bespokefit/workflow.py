"""
This is the main bespokefit workflow factory which is executed and builds the bespoke workflows.
"""

from typing import List, Optional, Union

from openforcefield import topology as off
from openforcefield.typing.engines.smirnoff import get_available_force_fields
from pydantic import BaseModel, Field, validator

from openff.bespokefit.exceptions import ForceFieldError, OptimizerError
from openff.bespokefit.fragmentation import (
    FragmentEngine,
    WBOFragmenter,
    get_fragment_engine,
)
from openff.bespokefit.optimizers import get_optimizer, list_optimizers
from openff.bespokefit.optimizers.model import Optimizer
from openff.bespokefit.schema.fitting import (
    FittingSchema,
    MoleculeSchema,
    OptimizationSchema,
)
from openff.bespokefit.utils import deduplicated_list
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
        False,
        description="If the optimization should first expand the number of k values that should be fit for each torsion beyond what is in the initial force field.",
    )
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
    )  # the driver type will be appended to the name
    optimizer: Optional[Optimizer] = Field(
        None,
        description="The optimizer that should be used with the targets already set.",
    )
    fragmentation_engine: Optional[FragmentEngine] = Field(
        WBOFragmenter(),
        description="The Fragment engine that should be used to fragment the molecule, note that if None is "
        "provided the molecules will not be fragmented. By default we use the WBO fragmenter by openforcefield.",
    )

    class Config:
        validate_assignment = True
        allow_mutation = True
        arbitrary_types_allowed = True

    @validator("initial_forcefield")
    def check_forcefield(cls, forcefield: str) -> str:
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
            fragmenter = get_fragment_engine(**fragmentation_engine)
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

    def create_fitting_schema(
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
        molecules: Union[off.Molecule, List[off.Molecule]]
            The molecule or list of molecules which should be processed by the schema to generate the fitting schema.
        """
        from multiprocessing.pool import Pool

        # check we have an optimizer in the pipeline
        if self.optimizer is None:
            raise OptimizerError(
                "No optimizer has been set please set it using `set_optimizer`"
            )

        # now check we have targets in each optimizer
        if not self.optimizer.optimization_targets:
            raise OptimizerError(
                f"There are no optimization targets for the optimizer {self.optimizer.optimizer_name} in the optimization workflow."
            )

        # create a deduplicated list of molecules first.
        deduplicated_molecules = deduplicated_list(molecules=molecules)

        fitting_schema = FittingSchema(
            client=self.client,
            torsiondrive_dataset_name=self.torsiondrive_dataset_name,
            optimization_dataset_name=self.optimization_dataset_name,
            singlepoint_dataset_name=self.singlepoint_dataset_name,
        )
        # add the settings for the optimizer
        fitting_schema.add_optimizer(self.optimizer)

        # now set up a process pool to do fragmentation and create the fitting schema while retaining
        # the original fitting order
        if processors is None or processors > 1:
            with Pool() as pool:
                schema_list = {
                    (i, pool.apply_async(self.create_task_schema, (molecule, i)))
                    for i, molecule in enumerate(deduplicated_molecules)
                }
                for i, molecule in enumerate(deduplicated_molecules.molecules):
                    # for each molecule make the fitting schema
                    mol_name = molecule.to_smiles(mapped=True)
                    molecule_schema = MoleculeSchema(
                        molecule=mol_name,
                        initial_forcefield=self.initial_forcefield,
                        task_id=f"bespoke_task_{i}",
                    )
                    # Make a workflow for each molecule/optimizer combination
                    workflow_stage = OptimizationSchema(
                        optimizer_name=self.optimizer.optimizer_name,
                        job_id=f"{self.optimizer.optimizer_name}",
                    )
                    # now add all the targets associated with the optimizer
                    for target in self.optimizer.optimization_targets:
                        target_entry = target.generate_fitting_schema(
                            molecule=molecule,
                            initial_ff_values=self.initial_forcefield,
                            expand_torsion_terms=self.expand_torsion_terms,
                        )
                        workflow_stage.targets.append(target_entry)
                    molecule_schema.workflow = workflow_stage
                    fitting_schema.add_molecule_schema(molecule_schema)

        return fitting_schema

    def create_task_schema(self, molecule: off.Molecule, index: int) -> MoleculeSchema:
        """
        For the given molecule run the fragmentation and generate the Molecule schema.
        """
        mol_name = molecule.to_smiles(mapped=True)
        molecule_schema = MoleculeSchema(
            molecule=mol_name,
            initial_forcefield=self.initial_forcefield,
            task_id=f"bespoke_task_{index}",
        )
        # Make a workflow for each molecule/optimizer combination
        workflow_stage = OptimizationSchema(
            optimizer_name=self.optimizer.optimizer_name,
            job_id=f"{self.optimizer.optimizer_name}",
        )
        if self.fragmentation_engine is not None:
            fragment_data = self.fragmentation_engine.fragment(molecule=molecule)
        else:
            fragment_data = [
                molecule,
            ]

        # now for each target make the target schema which details the target properties
        for target in self.optimizer.optimization_targets:
            target_schema = target.target_schema()

        return molecule_schema
