import importlib
import logging
import os
import subprocess
from typing import Any, Dict

from openff.utilities.provenance import get_ambertools_version

from openff.bespokefit.optimizers.forcebalance import ForceBalanceInputFactory
from openff.bespokefit.optimizers.model import BaseOptimizer, OptimizerResultsType
from openff.bespokefit.schema import Error
from openff.bespokefit.schema.fitting import (
    BaseOptimizationSchema,
    BespokeOptimizationSchema,
    OptimizationSchema,
)
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.results import (
    BespokeOptimizationResults,
    OptimizationResults,
)
from openff.bespokefit.schema.targets import (
    AbInitioTargetSchema,
    OptGeoTargetSchema,
    TorsionProfileTargetSchema,
    VibrationTargetSchema,
)
from openff.bespokefit.utilities.smirnoff import ForceFieldEditor

_logger = logging.getLogger(__name__)


class ForceBalanceOptimizer(BaseOptimizer):
    """
    An optimizer class which controls the interface with ForceBalance.
    """

    @classmethod
    def name(cls) -> str:
        return "ForceBalance"

    @classmethod
    def description(cls) -> str:
        return (
            "A systematic force field optimization tool: "
            "https://github.com/leeping/forcebalance"
        )

    @classmethod
    def provenance(cls) -> Dict:
        """
        Collect the provenance information for forcebalance.
        """
        import forcebalance
        import openff.toolkit

        versions = {
            "forcebalance": forcebalance.__version__,
            "openff.toolkit": openff.toolkit.__version__,
        }

        try:
            import openeye

            versions["openeye"] = openeye.__version__
        except ImportError:
            pass

        ambertools_version = get_ambertools_version()

        if ambertools_version is not None:
            versions["ambertools"] = ambertools_version

        return versions

    @classmethod
    def is_available(cls) -> bool:
        try:
            importlib.import_module("forcebalance")
            return True
        except ImportError:
            return False

    @classmethod
    def _schema_class(cls):
        return ForceBalanceSchema

    @classmethod
    def _prepare(cls, schema: BaseOptimizationSchema, root_directory: str):
        """The internal implementation of the main ``prepare`` method. The input
        ``schema`` is assumed to have been validated before being passed to this
        method.
        """

        _logger.info(f"making new fb folders in {root_directory}")
        ForceBalanceInputFactory.generate(root_directory, schema)

    @classmethod
    def _optimize(cls, schema: BaseOptimizationSchema) -> OptimizerResultsType:

        # execute forcebalanace to fit the molecule
        with open("log.txt", "w") as log:

            _logger.debug("Launching Forcebalance")

            subprocess.run(
                "ForceBalance optimize.in",
                shell=True,
                stdout=log,
                stderr=log,
            )

            results = cls._collect_results("", schema=schema)

        _logger.debug("OPT finished in folder", os.getcwd())
        return results

    @classmethod
    def _collect_results(
        cls, root_directory: str, schema: BaseOptimizationSchema
    ) -> OptimizerResultsType:
        """Collect the results of a ForceBalance optimization.

        Check the exit state of the optimization before attempting to update the final
        smirks parameters.

        Parameters
        ----------
        root_directory
            The path to the root directory of the ForceBalance optimization.
        schema
            The workflow schema that should be updated with the results of the current
            optimization.

        Returns
        -------
            The results of the optimization.
        """

        # look for the result
        results_dictionary = cls._read_output(root_directory)

        # TODO: Should the provenance dictionary contain also any task
        #       provenance?

        force_field_editor = ForceFieldEditor(results_dictionary["forcefield"])

        if isinstance(schema, BespokeOptimizationSchema):

            results = BespokeOptimizationResults(
                input_schema=schema,
                provenance=cls.provenance(),
                status=results_dictionary["status"],
                error=results_dictionary["error"],
                refit_force_field=force_field_editor.force_field.to_string(
                    discard_cosmetic_attributes=True
                ),
            )

        elif isinstance(schema, OptimizationSchema):

            results = OptimizationResults(
                input_schema=schema,
                provenance=cls.provenance(),
                status=results_dictionary["status"],
                error=results_dictionary["error"],
                refit_force_field=force_field_editor.force_field.to_string(
                    discard_cosmetic_attributes=True
                ),
            )

        else:
            raise NotImplementedError()

        return results

    @classmethod
    def _read_output(cls, root_directory) -> Dict[str, Any]:
        """Read the output file of the ForceBalance job to determine the exit state of
        the fitting and the name of the optimized force field.

        Parameters
        ----------
        root_directory
            The path to the root directory of the ForceBalance optimization.

        Returns
        -------
        Dict[str, str]
            A dictionary containing the exit status of the optimization and the file
            path to the optimized forcefield.
        """

        result = {"error": None}

        with open(os.path.join(root_directory, "optimize.out")) as log:

            for line in log.readlines():

                if "optimization converged" in line.lower():

                    result["status"] = "success"
                    break

                elif "convergence failure" in line.lower():

                    result["status"] = "errored"

                    result["error"] = Error(
                        type="ConvergenceFailure",
                        message="The optimization failed to converge.",
                    )

                    break

            else:

                result["status"] = "running"

        force_field_dir = os.path.join(root_directory, "result", "optimize")
        result["forcefield"] = os.path.join(force_field_dir, "force-field.offxml")

        return result


# register all of the available targets.
ForceBalanceOptimizer.register_target(AbInitioTargetSchema)
ForceBalanceOptimizer.register_target(TorsionProfileTargetSchema)
ForceBalanceOptimizer.register_target(OptGeoTargetSchema)
ForceBalanceOptimizer.register_target(VibrationTargetSchema)
