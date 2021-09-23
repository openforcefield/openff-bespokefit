"""
This is the main bespokefit workflow factory which is executed and builds the bespoke
workflows.
"""
import logging
import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Union

from openff.fragmenter.fragment import WBOFragmenter
from openff.qcsubmit.common_structures import QCSpec
from openff.qcsubmit.results import (
    BasicResultCollection,
    OptimizationResultCollection,
    TorsionDriveResultCollection,
)
from openff.qcsubmit.serializers import serialize
from openff.qcsubmit.workflow_components import ComponentResult
from openff.toolkit.topology import Molecule
from openff.toolkit.typing.engines.smirnoff import (
    AngleHandler,
    BondHandler,
    ForceField,
    ImproperTorsionHandler,
    ParameterType,
    ProperTorsionHandler,
    vdWHandler,
)
from pydantic import Field, validator
from qcelemental.models.common_models import Model
from qcportal.models import OptimizationRecord, ResultRecord, TorsionDriveRecord

from openff.bespokefit.exceptions import (
    FragmenterError,
    OptimizerError,
    TargetNotSetError,
)
from openff.bespokefit.fragmentation import FragmentationEngine
from openff.bespokefit.optimizers import get_optimizer, list_optimizers
from openff.bespokefit.schema.data import LocalQCData
from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.optimizers import ForceBalanceSchema, OptimizerSchema
from openff.bespokefit.schema.smirnoff import (
    AngleSMIRKS,
    BondSMIRKS,
    ImproperTorsionSMIRKS,
    ProperTorsionHyperparameters,
    ProperTorsionSMIRKS,
    SMIRNOFFHyperparameters,
    VdWSMIRKS,
)
from openff.bespokefit.schema.targets import (
    BespokeQCData,
    TargetSchema,
    TorsionProfileTargetSchema,
)
from openff.bespokefit.schema.tasks import (
    HessianTaskSpec,
    OptimizationTaskSpec,
    Torsion1DTaskSpec,
)
from openff.bespokefit.utilities import parallel
from openff.bespokefit.utilities.pydantic import ClassBase
from openff.bespokefit.utilities.smirks import (
    SMIRKSGenerator,
    SMIRKSType,
    validate_smirks,
)
from openff.bespokefit.utilities.smirnoff import ForceFieldEditor

QCResultRecord = Union[ResultRecord, OptimizationRecord, TorsionDriveRecord]
QCResultCollection = Union[
    TorsionDriveResultCollection,
    OptimizationResultCollection,
    BasicResultCollection,
]

_logger = logging.getLogger(__name__)

_DEFAULT_ROTATABLE_SMIRKS = "[!#1]~[!$(*#*)&!D1:1]-,=;!@[!$(*#*)&!D1:2]~[!#1]"


class BespokeWorkflowFactory(ClassBase):
    """The bespokefit workflow factory which is a template of the settings that will be
    used to generate the specific fitting schema for each molecule.
    """

    initial_force_field: str = Field(
        "openff_unconstrained-1.3.0.offxml",
        description="The name of the unconstrained force field to use as a starting "
        "point for optimization. The force field must be conda installed.",
    )

    optimizer: Union[str, OptimizerSchema] = Field(
        ForceBalanceSchema(penalty_type="L1"),
        description="The optimizer that should be used with the targets already set.",
    )

    target_templates: List[TargetSchema] = Field(
        [TorsionProfileTargetSchema()],
        description="Templates for the fitting targets to use as part of the "
        "optimization. The ``reference_data`` attribute of each schema will be "
        "automatically populated by this factory.",
    )

    parameter_hyperparameters: List[SMIRNOFFHyperparameters] = Field(
        [
            ProperTorsionHyperparameters(),
        ],
        description="The settings which describe how types of parameters, e.g. the "
        "force constant of a bond parameter, should be restrained during the "
        "optimisation such as through the inclusion of harmonic priors.",
    )

    target_torsion_smirks: List[str] = Field(
        [_DEFAULT_ROTATABLE_SMIRKS],
        description="A list of SMARTS patterns that should be used to identify the "
        "**bonds** within the target molecule to generate bespoke torsions around. Each "
        "SMARTS pattern should include **two** indexed atoms that correspond to the "
        "two atoms involved in the central bond."
        "\n"
        "By default bespoke torsion parameters (if requested) will be constructed for "
        "all non-terminal 'rotatable bonds'",
    )
    target_smirks: List[SMIRKSType] = Field(
        [
            SMIRKSType.ProperTorsions,
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

    fragmentation_engine: Optional[FragmentationEngine] = Field(
        WBOFragmenter(),
        description="The Fragment engine that should be used to fragment the molecule, "
        "note that if None is provided the molecules will not be fragmented. By default "
        "we use the WBO fragmenter by the Open Force Field Consortium.",
    )

    @validator("initial_force_field")
    def _check_force_field(cls, force_field: str) -> str:
        """Check that the force field is available via the toolkit."""
        assert ForceField(force_field) is not None
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

    @validator("target_torsion_smirks")
    def _check_target_torsion_smirks(cls, values: List[str]) -> List[str]:
        return [validate_smirks(value, 2) for value in values]

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
        elif len(self.parameter_hyperparameters) == 0:
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

    def export_factory(self, file_name: str) -> None:
        """
        Export the factory to yaml or json file.

        Parameters
        ----------
        file_name: str
            The name of the file the workflow should be exported to, the type is
            determined from the name.
        """

        serialize(serializable=self.dict(), file_name=file_name)

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
        processors: Optional[int] = 1,
    ) -> List[BespokeOptimizationSchema]:
        """This is the main function of the workflow which takes the general fitting
        meta-template and generates a specific one for the set of molecules that are
        passed.

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

        # TODO: Expand to accept the QCSubmit results datasets directly to create the
        #       fitting schema and fill the tasks.
        # TODO: How do we support dihedral tagging?

        # create a deduplicated list of molecules first.
        deduplicated_molecules = self._deduplicated_list(molecules=molecules).molecules

        optimization_schemas = [
            schema
            for schema in parallel.apply_async(
                self.optimization_schema_from_molecule,
                [(molecule, i) for i, molecule in enumerate(deduplicated_molecules)],
                n_processes=processors,
                verbose=True,
                description="Building Fitting Schema",
            )
            if schema is not None
        ]

        return optimization_schemas

    def optimization_schema_from_molecule(
        self, molecule: Molecule, index: int = 0
    ) -> Optional[BespokeOptimizationSchema]:
        """Build an optimization schema from an input molecule this involves
        fragmentation.
        """

        # make sure all required variables have been declared
        self._pre_run_check()

        return self._build_optimization_schema(molecule=molecule, index=index)

    def optimization_schemas_from_results(
        self,
        results: QCResultCollection,
        combine: bool = False,
        processors: Optional[int] = 1,
    ) -> List[BespokeOptimizationSchema]:
        """
        Create a set of optimization schemas (one per molecule) from some results.

        Here input molecules are turned into tasks and results are updated during the
        process.

        If multiple targets are in the workflow the results will be applied to the
        correct target other targets can be updated after by calling update with
        parameters.
        """

        # group the tasks if requested
        sorted_records = self._group_records(results.to_records(), combine)

        optimization_schemas = [
            schema
            for schema in parallel.apply_async(
                self._optimization_schema_from_records,
                [(records, i) for i, records in enumerate(sorted_records)],
                n_processes=processors,
                verbose=True,
                description="Building Fitting Schema",
            )
            if schema is not None
        ]

        return optimization_schemas

    @classmethod
    def _group_records(
        cls, records: List[Tuple[QCResultRecord, Molecule]], combine
    ) -> List[List[Tuple[QCResultRecord, Molecule]]]:
        """Group the result records into a list that can be processed into a fitting
        schema, combining results collected for the same molecule when requested.
        """

        if not combine:
            return [[record] for record in records]

        combined_records = []

        # loop over the results and combine multiple results for the same molecule
        # this only effects multiple torsion drives
        per_molecule_records = defaultdict(list)

        for record, molecule in records:

            inchi_key = molecule.to_inchikey(fixed_hydrogens=True)
            per_molecule_records[inchi_key].append((record, molecule))

        for unique_records in per_molecule_records.values():
            combined_records.append(unique_records)

        return combined_records

    def _optimization_schema_from_records(
        self,
        records: List[Tuple[QCResultRecord, Molecule]],
        index: int,
    ) -> BespokeOptimizationSchema:
        """
        Create an optimization task for a given list of results.

        Notes:
            * This method assumes a result records were generated for the same molecule.
            * The list allows multiple results to be combined from the same molecule
              which is mostly useful for torsion drives.
        """

        assert (
            len({molecule.to_inchikey(fixed_hydrogens=True) for _, molecule in records})
            == 1
        ), "all records must be for the same molecule"

        records_by_type = defaultdict(list)

        for record_tuple in records:
            records_by_type[record_tuple[0].__class__].append(record_tuple)

        local_qc_data = {}

        for record_type, records_of_type in records_by_type.items():

            record_type_label = {TorsionDriveRecord: "torsion1d"}[record_type]

            local_qc_data[record_type_label] = LocalQCData.from_remote_records(
                records_of_type
            )

        smirks_gen = self._get_smirks_generator()
        bespoke_parameters = []

        for record, record_molecule in records:

            if not isinstance(record, TorsionDriveRecord):
                raise NotImplementedError("Only torsion drives are supported.")

            dihedrals = record.keywords.dihedrals
            assert len(dihedrals) == 1, "only 1D torsion drives are supported"

            bespoke_parameters.extend(
                smirks_gen.generate_smirks_from_molecule(
                    molecule=record_molecule,
                    central_bond=(dihedrals[0][1], dihedrals[0][2]),
                )
            )

        opt_schema = self._build_optimization_schema(
            molecule=records[0][1],
            index=index,
            bespoke_parameters=bespoke_parameters,
            local_qc_data=local_qc_data,
        )

        return opt_schema

    def _default_bespoke_parameters(self, molecule: Molecule) -> List[ParameterType]:
        """Generates a default set of bespoke parameters to train for a given molecule
        of interest."""

        bespoke_parameters = []
        target_smirks = {*self.target_smirks}

        if SMIRKSType.ProperTorsions in self.target_smirks:

            target_smirks.remove(SMIRKSType.ProperTorsions)

            torsion_smirks_gen = self._get_smirks_generator(
                target_smirks=[SMIRKSType.ProperTorsions]
            )

            central_bonds = {
                tuple(sorted(match))
                for smirks in self.target_torsion_smirks
                for match in molecule.chemical_environment_matches(smirks)
            }

            bespoke_torsion_parameters = [
                parameter
                for match in central_bonds
                for parameter in torsion_smirks_gen.generate_smirks_from_molecule(
                    molecule, central_bond=match
                )
            ]
            bespoke_parameters.extend(bespoke_torsion_parameters)

        if len(target_smirks) > 0:

            smirks_gen = self._get_smirks_generator([*target_smirks])

            bespoke_parameters.extend(
                smirks_gen.generate_smirks_from_molecule(molecule)
            )

        return bespoke_parameters

    def _get_smirks_generator(
        self, target_smirks: Optional[List[SMIRKSType]] = None
    ) -> SMIRKSGenerator:
        """
        Build a smirks generator from the set of inputs.
        """
        smirks_gen = SMIRKSGenerator(
            initial_force_field=self.initial_force_field,
            generate_bespoke_terms=self.generate_bespoke_terms,
            expand_torsion_terms=self.expand_torsion_terms,
            target_smirks=self.target_smirks
            if target_smirks is None
            else target_smirks,
        )
        return smirks_gen

    def _build_optimization_schema(
        self,
        molecule: Molecule,
        index: int,
        bespoke_parameters: Optional[List[ParameterType]] = None,
        local_qc_data: Optional[Dict[str, LocalQCData]] = None,
    ) -> BespokeOptimizationSchema:
        """For a given molecule schema build an optimization schema."""

        # Determine the bespoke parameters to be trained.
        if bespoke_parameters is None:
            bespoke_parameters = self._default_bespoke_parameters(molecule)

        force_field_editor = ForceFieldEditor(self.initial_force_field)
        bespoke_parameters = force_field_editor.add_parameters(bespoke_parameters)

        parameter_to_type = {
            vdWHandler.vdWType: VdWSMIRKS,
            BondHandler.BondType: BondSMIRKS,
            AngleHandler.AngleType: AngleSMIRKS,
            ProperTorsionHandler.ProperTorsionType: ProperTorsionSMIRKS,
            ImproperTorsionHandler.ImproperTorsionType: ImproperTorsionSMIRKS,
        }
        # noinspection PyTypeChecker
        parameters = [
            parameter_to_type[parameter.__class__].from_smirnoff(parameter)
            for parameter in bespoke_parameters
        ]

        # Populate the targets
        targets = []

        task_type_to_spec = {
            "torsion1d": Torsion1DTaskSpec,
            "optimization": OptimizationTaskSpec,
            "hessian": HessianTaskSpec,
        }
        default_qc_spec = QCSpec()

        local_qc_data = {} if local_qc_data is None else local_qc_data

        for target_template in self.target_templates:

            target_schema = target_template.copy(deep=True)
            targets.append(target_schema)

            if target_schema.reference_data is not None:
                continue

            task_type = target_schema.bespoke_task_type()

            if task_type in local_qc_data:
                target_schema.reference_data = local_qc_data[task_type]
                continue

            target_schema.reference_data = BespokeQCData(
                spec=task_type_to_spec[task_type](
                    model=Model(
                        method=default_qc_spec.method, basis=default_qc_spec.basis
                    ),
                    program=default_qc_spec.program,
                )
            )

        schema = BespokeOptimizationSchema(
            id=f"bespoke_task_{index}",
            smiles=molecule.to_smiles(mapped=True),
            initial_force_field=force_field_editor.force_field.to_string(),
            optimizer=self.optimizer,
            parameters=parameters,
            parameter_hyperparameters=self.parameter_hyperparameters,
            targets=targets,
            fragmentation_engine=self.fragmentation_engine,
        )
        return schema
