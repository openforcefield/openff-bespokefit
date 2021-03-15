from typing import Dict, List, Optional, Union

from openff.qcsubmit.common_structures import QCSpec
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
    OptimizationCollectionResult,
    TorsionDriveCollectionResult,
)
from pydantic import Field, PositiveInt, validator
from qcelemental.models import DriverEnum
from typing_extensions import Literal

from openff.bespokefit.exceptions import DihedralSelectionError, MoleculeMissMatchError
from openff.bespokefit.schema.bespoke.tasks import FittingTask
from openff.bespokefit.utilities.pydantic import SchemaBase


class BespokeQCData(SchemaBase):

    type: Literal["bespoke"] = "bespoke"

    qc_spec: QCSpec = Field(
        QCSpec(),
        description="The QC specification that should be used to generate the reference "
        "data.",
    )
    target_conformers: PositiveInt = Field(
        4,
        description="The number of conformers that should be generated for this target.",
    )

    tasks: List[FittingTask] = Field(
        [],
        description="The QCSubmit tasks to be run to generate the reference QC data.",
    )

    @property
    def ready_for_fitting(self) -> bool:
        """Return whether all of the tasks have been successfully completed and
        collected.
        """
        return all(task.collected for task in self.tasks)

    @validator("tasks")
    def _check_tasks(cls, values: List[FittingTask]):

        task_types = set()

        for task_index, task in enumerate(values):
            task.name = f"{task.task_type}-{task_index}"
            task_types.add(task.task_type)

        assert (
            len(task_types) < 2
        ), f"all tasks must be of the same type (found={task_types})"

        return values

    def compare_qcspec(self, result) -> bool:
        """Make sure the qcspec from the results match the targeted qcspec."""

        return (
            result.program.lower() == self.qc_spec.program.lower()
            and result.method.lower() == self.qc_spec.method.lower()
            and result.basis.lower() == self.qc_spec.basis.lower()
            if result.basis is not None
            else result.basis == self.qc_spec.basis
        )

    def get_qcsubmit_tasks(
        self,
    ) -> List[Union[TorsionDriveEntry, OptimizationEntry, DatasetEntry]]:
        """Gather the qcsubmit tasks for the entries in this data set.

        Make sure we deduplicate the jobs which should make it easier to build the
        dataset.
        """
        tasks = dict()

        for task in self.tasks:
            job = task.get_qcsubmit_task()
            if job is not None:
                if job.attributes.task_hash not in tasks:
                    tasks[job.attributes.task_hash] = job

        return list(tasks.values())

    def build_qcsubmit_dataset(
        self,
    ) -> Optional[Union[OptimizationDataset, TorsiondriveDataset, BasicDataset]]:
        """Build a qcsubmit dataset from the qcsubmit tasks associated with this target
        and collection type.

        Notes:
            This will return ``None`` if there are no tasks to collect.
        """

        if len(self.tasks) == 0:
            return None

        description = (
            "A bespoke-fit generated dataset to be used for parameter "
            "optimization for more information please visit "
            "https://github.com/openforcefield/bespoke-fit."
        )

        dataset_name = "OpenFF Bespoke-fit"

        task_type = self.tasks[0].task_type

        if task_type == "torsion1d":
            dataset = TorsiondriveDataset(
                dataset_name=dataset_name,
                qc_specifications={},
                description=description,
                driver=DriverEnum.gradient,
            )
        elif task_type == "optimization":
            dataset = OptimizationDataset(
                dataset_name=dataset_name,
                qc_specifications={},
                description=description,
                driver=DriverEnum.gradient,
            )
        elif task_type == "hessian":
            dataset = BasicDataset(
                dataset_name=dataset_name,
                qc_specifications={},
                description=description,
                driver=DriverEnum.hessian,
            )
        else:
            raise NotImplementedError(
                f"The collection workflow {task_type} does not have a supported "
                f"qcsubmit dataset type."
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
            # TODO: add an api point to qcsubmit to allow adding dataset entries,
            #       this would also validate the entry type.
            dataset.metadata.elements.update(task.initial_molecules[0].symbols)

        if dataset.n_records > 0:
            return dataset

        return None

    def update_with_results(
        self,
        results: Union[
            BasicCollectionResult,
            OptimizationCollectionResult,
            TorsionDriveCollectionResult,
        ],
    ):
        """
        Take a list of results and work out if they can be mapped on the the target.
        """

        if len(self.tasks) == 0:
            return

        expected_task_type = self.tasks[0].task_type

        # make sure the result type matches the collection workflow allowed types
        if (
            results.__class__ == TorsionDriveCollectionResult
            and expected_task_type != "torsion1d"
        ):
            raise Exception("Torsion1d workflow requires torsiondrive results.")
        elif (
            results.__class__ != TorsionDriveCollectionResult
            and expected_task_type == "torsion1d"
        ):
            raise Exception(
                "Optimization and hessian workflows require optimization and basic "
                "dataset results"
            )
        elif (
            results.__class__ == BasicCollectionResult
            and results.driver != expected_task_type
        ):
            raise Exception(
                "Hessian results must be computed using the hessian driver."
            )

        # check the QC method matches what we targeted
        if not self.compare_qcspec(results):
            raise Exception(
                "The results could not be saved as the qcspec did not match"
            )

        # we now know the specification and result type match so try and apply the
        # results
        for result in results.collection.values():
            for task in self.tasks:
                try:
                    task.update_with_results(result)
                except (DihedralSelectionError, MoleculeMissMatchError):
                    continue

    def get_task_map(self) -> Dict[str, List[FittingTask]]:
        """Generate a mapping between all current tasks and their task hash."""

        hash_map = dict()
        for task in self.tasks:
            if not task.collected:
                task_hash = task.get_task_hash()
                hash_map.setdefault(task_hash, []).append(task)

        return hash_map


class ExistingQCData(SchemaBase):

    type: Literal["existing"] = "existing"

    record_ids: List[str] = Field(
        ..., description="The ids of the QC records to include in the fitting target."
    )

    qcfractal_address: Optional[str] = Field(
        "api.qcarchive.molssi.org:443",
        description="The URL of the QCFractal server to pull the results from. By "
        "default the main QCArchive will be used.",
    )
