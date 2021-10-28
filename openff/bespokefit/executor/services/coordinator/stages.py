import abc
import json
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Optional, Union

import httpx
from openff.fragmenter.fragment import FragmentationResult
from openff.toolkit.typing.engines.smirnoff import ParameterType
from pydantic import Field
from qcelemental.models import AtomicResult, OptimizationResult
from qcelemental.util import serialize
from qcengine.procedures.torsiondrive import TorsionDriveResult
from typing_extensions import Literal

from openff.bespokefit.executor.services import settings
from openff.bespokefit.executor.services.fragmenter.models import (
    FragmenterGETResponse,
    FragmenterPOSTBody,
    FragmenterPOSTResponse,
)
from openff.bespokefit.executor.services.optimizer.models import (
    OptimizerGETResponse,
    OptimizerPOSTBody,
    OptimizerPOSTResponse,
)
from openff.bespokefit.executor.services.qcgenerator.models import (
    QCGeneratorGETPageResponse,
    QCGeneratorPOSTBody,
    QCGeneratorPOSTResponse,
)
from openff.bespokefit.executor.utilities.typing import Status
from openff.bespokefit.schema.data import BespokeQCData, LocalQCData
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults
from openff.bespokefit.schema.smirnoff import ProperTorsionSMIRKS
from openff.bespokefit.schema.tasks import Torsion1DTask
from openff.bespokefit.utilities.pydantic import BaseModel
from openff.bespokefit.utilities.smirks import ForceFieldEditor, SMIRKSGenerator

if TYPE_CHECKING:
    from openff.bespokefit.executor.services.coordinator.models import CoordinatorTask


class _Stage(BaseModel, abc.ABC):

    type: Literal["base-stage"] = "base-stage"

    status: Status = Field("waiting", description="The status of this stage.")

    error: Optional[str] = Field(
        None, description="The error raised, if any, while running this stage."
    )

    @abc.abstractmethod
    async def enter(self, task: "CoordinatorTask"):
        pass

    @abc.abstractmethod
    async def update(self):
        pass


class FragmentationStage(_Stage):

    type: Literal["fragmentation"] = "fragmentation"

    id: Optional[str] = Field(None, description="")

    result: Optional[FragmentationResult] = Field(None, description="")

    async def enter(self, task: "CoordinatorTask"):

        async with httpx.AsyncClient() as client:

            raw_response = await client.post(
                f"http://127.0.0.1:"
                f"{settings.BEFLOW_GATEWAY_PORT}"
                f"{settings.BEFLOW_API_V1_STR}/"
                f"{settings.BEFLOW_FRAGMENTER_PREFIX}",
                data=FragmenterPOSTBody(
                    cmiles=task.input_schema.smiles,
                    fragmenter=task.input_schema.fragmentation_engine,
                    target_bond_smarts=task.input_schema.target_torsion_smirks,
                ).json(),
            )

            if raw_response.status_code != 200:

                self.error = json.dumps(raw_response.text)
                self.status = "errored"

                return

            contents = raw_response.text

        post_response = FragmenterPOSTResponse.parse_raw(contents)

        self.id = post_response.id

    async def update(self):

        if self.status == "errored":
            return

        async with httpx.AsyncClient() as client:

            raw_response = await client.get(
                f"http://127.0.0.1:"
                f"{settings.BEFLOW_GATEWAY_PORT}"
                f"{settings.BEFLOW_API_V1_STR}/"
                f"{settings.BEFLOW_FRAGMENTER_PREFIX}/{self.id}"
            )

            if raw_response.status_code != 200:

                self.error = json.dumps(raw_response.text)
                self.status = "errored"

                return

            contents = raw_response.text

        get_response = FragmenterGETResponse.parse_raw(contents)

        self.result = get_response.result

        self.error = get_response.error
        self.status = get_response.status


class QCGenerationStage(_Stage):

    type: Literal["qc-generation"] = "qc-generation"

    ids: Optional[Dict[int, List[str]]] = Field(None, description="")

    results: Optional[
        Dict[str, Union[AtomicResult, OptimizationResult, TorsionDriveResult]]
    ] = Field(None, description="")

    async def enter(self, task: "CoordinatorTask"):

        fragment_stage = next(
            iter(
                stage
                for stage in task.completed_stages
                if stage.type == "fragmentation"
            ),
            None,
        )
        fragments = [] if fragment_stage is None else fragment_stage.result.fragments

        target_qc_tasks = defaultdict(list)

        for i, target in enumerate(task.input_schema.targets):

            if not isinstance(target.reference_data, BespokeQCData):
                continue

            if target.bespoke_task_type() == "torsion1d":

                target_qc_tasks[i].extend(
                    Torsion1DTask(
                        smiles=fragment.smiles,
                        central_bond=fragment.bond_indices,
                        **target.reference_data.spec.dict(),
                    )
                    for fragment in fragments
                )

            else:
                raise NotImplementedError()

        qc_calc_ids = defaultdict(set)

        async with httpx.AsyncClient() as client:

            for i, qc_tasks in target_qc_tasks.items():

                for qc_task in qc_tasks:

                    raw_response = await client.post(
                        f"http://127.0.0.1:"
                        f"{settings.BEFLOW_GATEWAY_PORT}"
                        f"{settings.BEFLOW_API_V1_STR}/"
                        f"{settings.BEFLOW_QC_COMPUTE_PREFIX}",
                        data=QCGeneratorPOSTBody(input_schema=qc_task).json(),
                    )

                    if raw_response.status_code != 200:

                        self.error = json.dumps(raw_response.text)
                        self.status = "errored"

                        return

                    response = QCGeneratorPOSTResponse.parse_raw(raw_response.text)
                    qc_calc_ids[i].add(response.id)

        self.ids = {i: sorted(ids) for i, ids in qc_calc_ids.items()}

    async def update(self):

        if self.status == "errored":
            return

        async with httpx.AsyncClient() as client:

            id_query = "&ids=".join(qc_id for i in self.ids for qc_id in self.ids[i])

            raw_response = await client.get(
                f"http://127.0.0.1:"
                f"{settings.BEFLOW_GATEWAY_PORT}"
                f"{settings.BEFLOW_API_V1_STR}/"
                f"{settings.BEFLOW_QC_COMPUTE_PREFIX}?ids={id_query}"
            )
            contents = raw_response.text

            if raw_response.status_code != 200:

                self.error = json.dumps(raw_response.text)
                self.status = "errored"

                return

        get_responses = QCGeneratorGETPageResponse.parse_raw(contents).contents

        statuses = {get_response.status for get_response in get_responses}

        errors = [
            json.loads(get_response.error)
            for get_response in get_responses
            if get_response.error is not None
        ]

        self.error = json.dumps(errors)
        self.status = "running"

        if "errored" in statuses:
            self.status = "errored"

        elif statuses == {"waiting"}:
            self.status = "waiting"

        elif statuses == {"success"}:

            self.status = "success"

            self.results = {
                get_response.id: get_response.result for get_response in get_responses
            }


class OptimizationStage(_Stage):

    type: Literal["optimization"] = "optimization"

    id: Optional[str] = Field(
        None, description="The id of the optimization associated with this stage."
    )

    result: Optional[BespokeOptimizationResults] = Field(
        None, description="The result of the optimization."
    )

    @staticmethod
    def _regenerate_torsion_parameters(
        fragmentation_result: FragmentationResult,
        initial_force_field: str,
    ) -> List[ParameterType]:

        parent = fragmentation_result.parent_molecule
        smirks_gen = SMIRKSGenerator(initial_force_field=initial_force_field)

        new_smirks = []
        for fragment_data in fragmentation_result.fragments:
            central_bond = fragment_data.bond_indices
            fragment_molecule = fragment_data.molecule
            smirks = smirks_gen.generate_smirks_from_fragment(
                parent=parent,
                fragment=fragment_molecule,
                fragment_map_indices=central_bond,
            )
            new_smirks.extend(smirks)

        return new_smirks

    @staticmethod
    async def _regenerate_parameters(
        fragmentation_result: FragmentationResult,
        input_schema: BespokeOptimizationSchema,
    ):
        """
        Regenerate any place holder torsion parameters in the input schema and add them to the force field while
        removing old values. This edits the input schema in place.
        """

        initial_force_field = ForceFieldEditor(input_schema.initial_force_field)

        torsion_parameters = OptimizationStage._regenerate_torsion_parameters(
            fragmentation_result=fragmentation_result,
            initial_force_field=input_schema.initial_force_field,
        )

        torsion_handler = initial_force_field.force_field["ProperTorsions"]

        new_parameters = []
        # now we can remove all of the place holder terms
        for old_parameter in input_schema.parameters:
            if isinstance(old_parameter, ProperTorsionSMIRKS):
                # remove from the old force field
                del torsion_handler.parameters[old_parameter.smirks]
            else:
                # we want to keep the other parameters
                new_parameters.append(old_parameter)

        # now add our new parameters to the force field and the schema list
        for torsion_parameter in torsion_parameters:
            new_parameters.append(
                ProperTorsionSMIRKS(
                    smirks=torsion_parameter.smirks, attributes={"k1", "k2", "k3", "k4"}
                )
            )
            initial_force_field.add_parameters(parameters=[torsion_parameter])

        input_schema.parameters = new_parameters
        input_schema.initial_force_field = initial_force_field.force_field.to_string()

    @staticmethod
    async def _inject_bespoke_qc_data(
        qc_generation_stage: QCGenerationStage,
        input_schema: BespokeOptimizationSchema,
    ):

        for i, target in enumerate(input_schema.targets):

            local_qc_data = LocalQCData(
                qc_records=[
                    qc_generation_stage.results[result_id]
                    for result_id in qc_generation_stage.ids[i]
                ]
            )

            target.reference_data = local_qc_data

    async def enter(self, task: "CoordinatorTask"):

        completed_stages = {stage.type: stage for stage in task.completed_stages}

        input_schema = task.input_schema.copy(deep=True)

        # Regenerate any parameters that should target both the parent molecule and
        # its fragments
        fragmentation_stage: FragmentationStage = completed_stages["fragmentation"]

        # TODO: Move these methods onto the celery worker.
        try:
            await self._regenerate_parameters(fragmentation_stage.result, input_schema)
        except BaseException as e:  # lgtm [py/catch-base-exception]

            self.status = "errored"
            self.error = json.dumps(
                f"Failed to generate SMIRKS patterns that match both the parent and "
                f"torsion fragments: {str(e)}"
            )

            return

        # Map the generated QC results into a local QC data class and update the schema
        # to target these.
        qc_generation_stage: QCGenerationStage = completed_stages["qc-generation"]

        try:
            await self._inject_bespoke_qc_data(qc_generation_stage, input_schema)
        except BaseException as e:  # lgtm [py/catch-base-exception]

            self.status = "errored"
            self.error = json.dumps(
                f"Failed to inject the bespoke QC data into the optimization "
                f"schema: {str(e)}"
            )

            return

        async with httpx.AsyncClient() as client:

            raw_response = await client.post(
                f"http://127.0.0.1:"
                f"{settings.BEFLOW_GATEWAY_PORT}"
                f"{settings.BEFLOW_API_V1_STR}/"
                f"{settings.BEFLOW_OPTIMIZER_PREFIX}",
                data=serialize(
                    OptimizerPOSTBody(input_schema=input_schema), encoding="json"
                ),
            )

            if raw_response.status_code != 200:

                self.error = json.dumps(raw_response.text)
                self.status = "errored"

                return

            response = OptimizerPOSTResponse.parse_raw(raw_response.text)
            self.id = response.id

    async def update(self):

        if self.status == "errored":
            return

        async with httpx.AsyncClient() as client:

            raw_response = await client.get(
                f"http://127.0.0.1:"
                f"{settings.BEFLOW_GATEWAY_PORT}"
                f"{settings.BEFLOW_API_V1_STR}/"
                f"{settings.BEFLOW_OPTIMIZER_PREFIX}/{self.id}"
            )
            contents = raw_response.text

            if raw_response.status_code != 200:

                self.error = json.dumps(raw_response.text)
                self.status = "errored"

                return

        get_response = OptimizerGETResponse.parse_raw(contents)

        self.result = get_response.result
        self.error = get_response.error
        self.status = get_response.status


StageType = Union[FragmentationStage, QCGenerationStage, OptimizationStage]
