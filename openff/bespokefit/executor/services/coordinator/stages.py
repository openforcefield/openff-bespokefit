import abc
import json
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

import httpx
from chemper.graphs.cluster_graph import ClusterGraph
from openff.bespokefit.schema.data import BespokeQCData, LocalQCData
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults
from openff.bespokefit.schema.smirnoff import ProperTorsionSMIRKS, SMIRNOFFParameter
from openff.bespokefit.schema.tasks import Torsion1DTask
from openff.bespokefit.utilities.molecule import (
    get_atom_symmetries,
    group_valence_by_symmetry,
)
from openff.fragmenter.fragment import FragmentationResult
from openff.fragmenter.utils import get_map_index
from openff.toolkit.topology import Molecule
from openff.toolkit.typing.engines.smirnoff import ForceField
from pydantic import BaseModel, Field, parse_raw_as
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
    QCGeneratorGETResponse,
    QCGeneratorPOSTBody,
    QCGeneratorPOSTResponse,
)
from openff.bespokefit.executor.utilities.typing import Status

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

    @staticmethod
    def _generate_target_bond_smarts(
        smiles: str, parameters: List[SMIRNOFFParameter]
    ) -> List[str]:
        """Attempts to find all of the bonds in the molecule around which a bespoke
        torsion parameter is being trained."""
        molecule = Molecule.from_mapped_smiles(smiles)

        all_central_bonds = {
            tuple(sorted(central_bond))
            for parameter in parameters
            if isinstance(parameter, ProperTorsionSMIRKS)
            for (_, *central_bond, _) in molecule.chemical_environment_matches(
                parameter.smirks
            )
        }

        grouped_central_bonds = group_valence_by_symmetry(
            molecule, sorted(all_central_bonds)
        )
        unique_central_bonds = [group[0] for group in grouped_central_bonds.values()]

        target_bond_smarts = set()

        for central_bond in unique_central_bonds:

            molecule.properties["atom_map"] = {
                i: (j + 1) for j, i in enumerate(central_bond)
            }
            target_bond_smarts.add(molecule.to_smiles(mapped=True))

        return sorted(target_bond_smarts)

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
                    target_bond_smarts=self._generate_target_bond_smarts(
                        task.input_schema.smiles, task.input_schema.parameters
                    ),
                ).json(),
            )

            if raw_response.status_code != 200:

                self.error = json.dumps(raw_response.text)
                self.status = "errored"

                return

            contents = raw_response.text

        post_response = FragmenterPOSTResponse.parse_raw(contents)

        self.id = post_response.fragmentation_id

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

        self.result = get_response.fragmentation_result

        self.error = get_response.fragmentation_error
        self.status = get_response.fragmentation_status


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
                    qc_calc_ids[i].add(response.qc_calc_id)

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
                f"{settings.BEFLOW_QC_COMPUTE_PREFIX}s?ids={id_query}"
            )
            contents = raw_response.text

            if raw_response.status_code != 200:

                self.error = json.dumps(raw_response.text)
                self.status = "errored"

                return

        get_responses = parse_raw_as(List[QCGeneratorGETResponse], contents)

        statuses = {get_response.qc_calc_status for get_response in get_responses}

        errors = [
            json.loads(get_response.qc_calc_error)
            for get_response in get_responses
            if get_response.qc_calc_error is not None
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
                get_response.qc_calc_id: get_response.qc_calc_result
                for get_response in get_responses
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
        original_parameters: List[SMIRNOFFParameter],
        fragmentation_result: FragmentationResult,
    ) -> List[Tuple[ProperTorsionSMIRKS, ProperTorsionSMIRKS]]:

        parent = fragmentation_result.parent_molecule
        parent_atom_symmetries = get_atom_symmetries(parent)

        parent_map_symmetries = {
            get_map_index(parent, i): parent_atom_symmetries[i]
            for i in range(parent.n_atoms)
        }

        fragments = [fragment.molecule for fragment in fragmentation_result.fragments]

        fragment_by_symmetry = {
            tuple(
                sorted(parent_map_symmetries[i] for i in result.bond_indices)
            ): fragment
            for fragment, result in zip(fragments, fragmentation_result.fragments)
        }
        assert len(fragment_by_symmetry) == len(fragmentation_result.fragments)

        fragment_map_to_atom_index = [
            {j: i for i, j in fragment.properties.get("atom_map", {}).items()}
            for fragment in fragments
        ]

        return_value = []

        for original_parameter in original_parameters:

            if not isinstance(original_parameter, ProperTorsionSMIRKS):
                continue

            matches = parent.chemical_environment_matches(original_parameter.smirks)
            matches = list(
                set(
                    match if match[1] < match[2] else tuple(reversed(match))
                    for match in matches
                )
            )

            # Figure out which fragments need to be matched by this parameter and
            # update the parameter so it matches these AND the parent.
            match_symmetries = {
                tuple(sorted(parent_atom_symmetries[i] for i in match[1:3]))
                for match in matches
            }
            match_fragments = [
                fragment_by_symmetry[match_symmetry]
                for match_symmetry in match_symmetries
            ]

            target_atoms = [matches]
            target_molecules = [parent]

            for fragment, map_to_atom_index in zip(
                match_fragments, fragment_map_to_atom_index
            ):

                match_atoms = [
                    tuple(
                        map_to_atom_index.get(get_map_index(parent, i), None)
                        for i in match
                    )
                    for match in matches
                ]
                target_atoms.append(
                    [
                        match
                        for match in match_atoms
                        if all(i is not None for i in match)
                    ]
                )

                if len(target_atoms) == 0:
                    continue

                target_molecules.append(fragment)

            parameter = original_parameter.copy(deep=True)
            parameter.smirks = ClusterGraph(
                mols=[molecule.to_rdkit() for molecule in target_molecules],
                smirks_atoms_lists=target_atoms,
                layers="all",
            ).as_smirks(compress=False)

            return_value.append((original_parameter, parameter))

        return return_value

    async def _regenerate_parameters(
        self,
        fragmentation_stage: FragmentationStage,
        input_schema: BespokeOptimizationSchema,
    ):

        initial_force_field = ForceField(
            input_schema.initial_force_field, allow_cosmetic_attributes=True
        )

        torsion_parameters = self._regenerate_torsion_parameters(
            input_schema.parameters, fragmentation_stage.result
        )

        torsion_handler = initial_force_field["ProperTorsions"]

        for original_parameter, new_parameter in torsion_parameters:

            force_field_parameter = torsion_handler.parameters[
                original_parameter.smirks
            ]
            force_field_parameter.smirks = new_parameter.smirks

        input_schema.parameters = [
            *[
                parameter
                for parameter in input_schema.parameters
                if not isinstance(parameter, ProperTorsionSMIRKS)
            ],
            *[parameter for _, parameter in torsion_parameters],
        ]

        input_schema.initial_force_field = initial_force_field.to_string()

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
            await self._regenerate_parameters(fragmentation_stage, input_schema)
        except BaseException as e:

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
        except BaseException as e:

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
            self.id = response.optimization_id

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

        self.result = get_response.optimization_result
        self.error = get_response.optimization_error
        self.status = get_response.optimization_status


StageType = Union[FragmentationStage, QCGenerationStage, OptimizationStage]
