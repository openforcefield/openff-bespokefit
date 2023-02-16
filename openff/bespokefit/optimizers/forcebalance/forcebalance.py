import importlib
import logging
import os
import subprocess
import abc
from typing import Any, Dict

from openff.toolkit.typing.engines.smirnoff import ForceField
from openff.utilities.provenance import get_ambertools_version

from openff.bespokefit.optimizers.forcebalance import ForceBalanceInputFactory
from openff.bespokefit.optimizers.model import BaseOptimizer
from openff.bespokefit.schema import Error
from openff.bespokefit.schema.fitting import OptimizationStageSchema
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.results import OptimizationStageResults
from openff.bespokefit.schema.targets import (
    AbInitioTargetSchema,
    OptGeoTargetSchema,
    TorsionProfileTargetSchema,
    VibrationTargetSchema,
)
from openff.bespokefit.utilities.smirnoff import ForceFieldEditor

_logger = logging.getLogger(__name__)


class ForceBalanceOptimizerBase(BaseOptimizer):
    """
    An optimizer class which controls the interface with ForceBalance.
    """

    _module_path: str = None
    _cli_command: str = None

    @classmethod
    @abc.abstractmethod
    def _fb_version(cls) -> str:
        """Returns the version of ForceBalance."""
        raise NotImplementedError()

    @classmethod
    def provenance(cls) -> Dict:
        """
        Collect the provenance information for forcebalance.
        """
        import openff.forcebalance
        import openff.toolkit

        versions = {
            cls._module_path: cls._fb_version(),
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
            importlib.import_module(cls._module_path)
            return True
        except ImportError:
            return False

    @classmethod
    def _schema_class(cls):
        return ForceBalanceSchema

    @classmethod
    def _prepare(
        cls,
        schema: OptimizationStageSchema,
        initial_force_field: ForceField,
        root_directory: str,
    ):
        """The internal implementation of the main ``prepare`` method. The input
        ``schema`` is assumed to have been validated before being passed to this
        method.
        """

        _logger.info(f"making new fb folders in {root_directory}")
        ForceBalanceInputFactory.generate(root_directory, schema, initial_force_field)

    @classmethod
    def _optimize(
        cls, schema: OptimizationStageSchema, initial_force_field: ForceField
    ) -> OptimizationStageResults:

        with open("optimize.out", "w") as log:

            _logger.debug(f"Launching {cls.name()}")

            subprocess.run(
                cls._cli_command.format("optimize.in"),
                shell=True,
                stdout=log,
                stderr=log,
                check=True,
            )

            print("collecting forcebalance results")
            results = cls._collect_results("")

        _logger.debug("OPT finished in folder", os.getcwd())
        return results

    @classmethod
    def _collect_results(cls, root_directory: str) -> OptimizationStageResults:
        """Collect the results of a ForceBalance optimization.

        Check the exit state of the optimization before attempting to update the final
        smirks parameters.

        Parameters
        ----------
        root_directory
            The path to the root directory of the ForceBalance optimization.

        Returns
        -------
            The results of the optimization.
        """

        results_dictionary = cls._read_output(root_directory)

        force_field_editor = ForceFieldEditor(results_dictionary["forcefield"])

        results = OptimizationStageResults(
            provenance=cls.provenance(),
            status=results_dictionary["status"],
            error=results_dictionary["error"],
            refit_force_field=None
            if results_dictionary["error"] is not None
            else force_field_editor.force_field.to_string(
                discard_cosmetic_attributes=True
            ),
        )

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

        try:
            with open(os.path.join(root_directory, "optimize.err")) as err:
                errlog = err.read()
                if "Traceback" in errlog:
                    raise ValueError(f"{cls.name()} job failed: {errlog}")
        except IOError:
            pass

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


class OpenFFForceBalanceOptimizer(ForceBalanceOptimizerBase):
    _module_path = "openff.forcebalance"
    _cli_command = "openff-forcebalance optimize -i {}"

    @classmethod
    def name(cls) -> str:
        return "OpenFF ForceBalance"

    @classmethod
    def description(cls) -> str:
        return (
            "A systematic force field optimization tool: "
            "https://github.com/openforcefield/openff-forcebalance"
        )

    @classmethod
    def _fb_version(cls) -> str:
        import openff.forcebalance

        return openff.forcebalance.__version__


class ForceBalanceOptimizer(ForceBalanceOptimizerBase):
    _module_path = "forcebalance"
    _cli_command = "ForceBalance {}"

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
    def _fb_version(cls) -> str:
        import forcebalance

        return forcebalance.__version__


# register all of the available targets.
ForceBalanceOptimizer.register_target(AbInitioTargetSchema)
ForceBalanceOptimizer.register_target(TorsionProfileTargetSchema)
ForceBalanceOptimizer.register_target(OptGeoTargetSchema)
ForceBalanceOptimizer.register_target(VibrationTargetSchema)

# register all of the available targets.
OpenFFForceBalanceOptimizer.register_target(AbInitioTargetSchema)
OpenFFForceBalanceOptimizer.register_target(TorsionProfileTargetSchema)
OpenFFForceBalanceOptimizer.register_target(OptGeoTargetSchema)
OpenFFForceBalanceOptimizer.register_target(VibrationTargetSchema)
