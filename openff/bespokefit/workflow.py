"""
This is the main bespokefit workflow factory which is executed and builds the bespoke workflows.
"""

from typing import List, Union

from openforcefield import topology as off
from openforcefield.typing.engines.smirnoff import get_available_force_fields
from pydantic import BaseModel, validator
from qcsubmit.serializers import deserialize, serialize

from .exceptions import ForceFieldError, OptimizerError
from .optimizers import get_optimizer, list_optimizers
from .optimizers.model import Optimizer
from .schema.fitting import FittingSchema, MoleculeSchema, WorkflowSchema
from .utils import deduplicated_list


class WorkflowFactory(BaseModel):
    """
    The bespokefit workflow factory which is a template of the settings that will be used to generate the specific fitting schema for each molecule.
    """

    initial_forcefield: str = "openff_unconstrained-1.2.0.offxml"
    client: str = "snowflake"  # the type of client that should be used
    torsiondrive_dataset_name: str = "Bespokefit torsiondrives"
    optimization_dataset_name: str = "Bespokefit optimizations"
    singlepoint_dataset_name: str = (
        "Bespokefit single points"  # the driver type will be appended to the name
    )
    optimization_workflow: List[Optimizer] = []

    class Config:
        validate_assignment = True
        allow_mutation = True
        arbitrary_types_allowed = True

    @validator("initial_forcefield")
    def check_forcefield(cls, forcefield: str) -> str:
        """
        Check that the forcefield is available via the toolkit.
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
        optimization_workflow = data.pop("optimization_workflow")
        workflow = cls.parse_obj(data)
        # now we need to re init the optimizer and the targets
        for optimizer in optimization_workflow:
            opt_targets = optimizer.pop("optimization_targets")
            opt_engine = get_optimizer(**optimizer)
            opt_engine.clear_optimization_targets()
            for target in opt_targets:
                opt_engine.set_optimization_target(target=target["name"], **target)
            workflow.add_optimization_stage(opt_engine)

        return workflow

    def add_optimization_stage(self, optimizer: Union[str, Optimizer]) -> None:
        """
        Add an optimization stage to the workflow that will be executed in order.

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

        self.optimization_workflow.append(opt_engine)

    def remove_optimization_stage(self, optimizer: Union[str, Optimizer]) -> None:
        """
        Remove an optimizer from the list of optimization stages.

        Parameters
        ----------
        optimizer: Union[str, Optimizer]
            The optimizer that should be removed from the workflow.
        """
        # remove by name
        if isinstance(optimizer, Optimizer):
            opt_name = optimizer.optimizer_name.lower()
        else:
            opt_name = optimizer.lower()

        stage_to_remove = None
        # find the optimizer with this name and remove it
        for opt in self.optimization_workflow:
            if opt.optimizer_name.lower() == opt_name:
                stage_to_remove = opt
                break

        if stage_to_remove is not None:
            self.optimization_workflow.remove(stage_to_remove)
        else:
            raise OptimizerError(
                f"No optimizer could be found in the workflow with the name {opt_name}."
            )

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
        self, molecules: Union[off.Molecule, List[off.Molecule], str, List[str]]
    ) -> FittingSchema:
        """
        This is the main function of the workflow which takes the general fitting metatemplate and generates a specific
        one for the set of molecules that are passed.

        #TODO Expand to accept the QCSubmit results datasets directly to create the fitting schema and fill the tasks.

        Parameters
        ----------
        molecules: Union[off.Molecule, List[off.Molecule]]
            The molecule or list of molecules which should be processed by the schema to generate the fitting schema.
        """
        # check we have an optimizer in the pipeline
        if not self.optimization_workflow:
            raise OptimizerError(
                "There are no optimization stages in the optimization workflow, first add an optimizer and targets."
            )

        # now check we have targets in each optimizer
        for opt in self.optimization_workflow:
            if not opt.optimization_targets:
                raise OptimizerError(
                    f"There are no optimization targets for the optimizer {opt.optimizer_name} in the optimization workflow."
                )

        # create a deduplicated list of molecules first.
        deduplicated_molecules = deduplicated_list(molecules=molecules)

        fitting_schema = FittingSchema(
            client=self.client,
            torsiondrive_dataset_name=self.torsiondrive_dataset_name,
            optimization_dataset_name=self.optimization_dataset_name,
            singlepoint_dataset_name=self.singlepoint_dataset_name,
        )
        # add the settings for each of the optimizers
        for optimizer in self.optimization_workflow:
            fitting_schema.add_optimizer(optimizer)
        for molecule in deduplicated_molecules.molecules:
            # for each molecule make the fitting schema
            mol_name = molecule.to_smiles(mapped=True)
            molecule_schema = MoleculeSchema(
                molecule=mol_name,
                initial_forcefield=self.initial_forcefield,
            )
            # add each optimizer
            # TODO fix job id name for other optimizers
            for optimizer in self.optimization_workflow:
                workflow_stage = WorkflowSchema(
                    optimizer_name=optimizer.optimizer_name, job_id=mol_name + "-fb"
                )
                # now add all the targets associated with the optimizer
                for target in optimizer.optimization_targets:
                    target_entry = target.generate_fitting_schema(
                        molecule=molecule,
                    )
                    workflow_stage.targets.append(target_entry)
                molecule_schema.workflow.append(workflow_stage)
            fitting_schema.add_molecule_schema(molecule_schema)

        return fitting_schema
