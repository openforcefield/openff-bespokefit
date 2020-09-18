"""
This is the main bespokefit workflow factory which is executed and builds the bespoke workflows.
"""

from typing import List, Union

from openforcefield import topology as off
from pydantic import BaseModel

from qcsubmit.serializers import deserialize, serialize

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
    singlepoint_dataset_name: str = "Bespokefit single points"  # the driver type will be appended to the name
    optimization_workflow: List[Optimizer] = []

    class Config:
        validate_assignment = True
        allow_mutation = True
        arbitrary_types_allowed = True

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
        # now we need to re initi the optimizer and the targets
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
        """

        if isinstance(optimizer, str):
            # we can check for the optimizer and attach it
            opt_engine = get_optimizer(optimizer.lower())

        else:
            if optimizer.optimizer_name.lower() in list_optimizers():
                opt_engine = optimizer

            else:
                raise KeyError(
                    f"The requested optimizer {optimizer} was not registered with bespokefit."
                )

        self.optimization_workflow.append(opt_engine)

    def export_workflow(self, file_name: str) -> None:
        """
        Export the workflow to file.
        Parameters:
            file_name: The name of the file the workflow should be exported to, the type is determined from the name.
        """

        serialize(serializable=self.dict(), file_name=file_name)

    def create_fitting_schema(
        self, molecules: Union[off.Molecule, List[off.Molecule], str, List[str]]
    ) -> FittingSchema:
        """
        This is the main function of the workflow which takes the general fitting metatemplate and generates a specific one for the set of molecules that are passed.

        Here for each molecule for each target we should generate a collection job.

        Parameters:
            molecules: The molecule or list of molecules which should be processed by the schema to generate the fitting schema.
        """

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
                molecule=mol_name, initial_forcefield=self.initial_forcefield,
            )
            # add each optimizer
            # TODO fix job id name for other optimizers
            for optimizer in self.optimization_workflow:
                workflow_stage = WorkflowSchema(
                    optimizer_name=optimizer.optimizer_name, job_id=mol_name + "-fb"
                )
                # now add all the targets associated with the optimizer
                for target in optimizer.optimization_targets:
                    target_entry = target.generate_fitting_schema(molecule=molecule,)
                    workflow_stage.targets.append(target_entry)
                molecule_schema.workflow.append(workflow_stage)
            fitting_schema.add_molecule_schema(molecule_schema)

        return fitting_schema
