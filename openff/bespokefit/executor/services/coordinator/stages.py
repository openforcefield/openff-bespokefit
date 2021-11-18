import abc
import json
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Optional, Union

import httpx
from openff.fragmenter.fragment import FragmentationResult
from openff.toolkit.typing.engines.smirnoff import (
    AngleHandler,
    BondHandler,
    ImproperTorsionHandler,
    ParameterType,
    ProperTorsionHandler,
    vdWHandler,
)
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
from openff.bespokefit.schema.smirnoff import (
    AngleSMIRKS,
    BondSMIRKS,
    ImproperTorsionSMIRKS,
    ProperTorsionSMIRKS,
    VdWSMIRKS,
)
from openff.bespokefit.schema.tasks import Torsion1DTask
from openff.bespokefit.utilities.pydantic import BaseModel
from openff.bespokefit.utilities.smirks import (
    ForceFieldEditor,
    SMIRKSGenerator,
    SMIRKSType,
)

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

        targets = [
            target for stage in task.input_schema.stages for target in stage.targets
        ]

        for i, target in enumerate(targets):

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
    def _generate_torsion_parameters(
        fragmentation_result: FragmentationResult,
        input_schema: BespokeOptimizationSchema,
    ) -> List[ParameterType]:

        parent = fragmentation_result.parent_molecule
        smirks_gen = SMIRKSGenerator(
            initial_force_field=input_schema.initial_force_field,
            generate_bespoke_terms=input_schema.smirk_settings.generate_bespoke_terms,
            expand_torsion_terms=input_schema.smirk_settings.expand_torsion_terms,
            target_smirks=[SMIRKSType.ProperTorsions],
        )

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
    async def _generate_parameters(
        fragmentation_result: FragmentationResult,
        input_schema: BespokeOptimizationSchema,
    ):
        """
        Generate a list of parameters which are to be optimised, these are added to the input force field.
        The parameters are also added to the parameter list in each stage corresponding to the stage where they will be fit.
        """

        initial_force_field = ForceFieldEditor(input_schema.initial_force_field)
        new_parameters = []

        target_smirks = {*input_schema.target_smirks}
        if SMIRKSType.ProperTorsions in target_smirks:
            target_smirks.remove(SMIRKSType.ProperTorsions)

            torsion_parameters = OptimizationStage._generate_torsion_parameters(
                fragmentation_result=fragmentation_result,
                input_schema=input_schema,
            )
            new_parameters.extend(torsion_parameters)

        if len(target_smirks) > 0:
            smirks_gen = SMIRKSGenerator(
                initial_force_field=input_schema.initial_force_field,
                generate_bespoke_terms=input_schema.smirk_settings.generate_bespoke_terms,
                target_smirks=[*target_smirks],
                smirks_layers=1,
            )

            parameters = smirks_gen.generate_smirks_from_molecule(
                molecule=input_schema.molecule
            )
            new_parameters.extend(parameters)

        # add all new terms to the input force field
        initial_force_field.add_parameters(parameters=new_parameters)

        parameter_to_type = {
            vdWHandler.vdWType: VdWSMIRKS,
            BondHandler.BondType: BondSMIRKS,
            AngleHandler.AngleType: AngleSMIRKS,
            ProperTorsionHandler.ProperTorsionType: ProperTorsionSMIRKS,
            ImproperTorsionHandler.ImproperTorsionType: ImproperTorsionSMIRKS,
        }
        # convert all parameters to bespokefit types
        parameters_to_fit = defaultdict(list)
        for parameter in new_parameters:
            bespoke_parameter = parameter_to_type[parameter.__class__].from_smirnoff(
                parameter
            )
            parameters_to_fit[bespoke_parameter.type].append(bespoke_parameter)

        # set which parameters should be optimised in each stage
        for stage in input_schema.stages:
            for hyper_param in stage.parameter_hyperparameters:
                stage.parameters.extend(parameters_to_fit[hyper_param.type])

        input_schema.initial_force_field = initial_force_field.force_field.to_string()

    @staticmethod
    async def _inject_bespoke_qc_data(
        qc_generation_stage: QCGenerationStage,
        input_schema: BespokeOptimizationSchema,
    ):

        targets = [target for stage in input_schema.stages for target in stage.targets]

        for i, target in enumerate(targets):

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

        # Generate all parameters to be optimised
        fragmentation_stage: FragmentationStage = completed_stages["fragmentation"]

        # TODO: Move these methods onto the celery worker.
        try:
            await self._generate_parameters(fragmentation_stage.result, input_schema)
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
