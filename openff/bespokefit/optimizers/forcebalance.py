import os
import subprocess
from typing import Any, Dict, List

from jinja2 import Template
from pydantic import PositiveFloat, PositiveInt
from typing_extensions import Literal

from openff.bespokefit.common_structures import Status
from openff.bespokefit.exceptions import TargetNotSetError
from openff.bespokefit.forcefield_tools import ForceFieldEditor
from openff.bespokefit.optimizers.model import Optimizer
from openff.bespokefit.schema import OptimizationSchema
from openff.bespokefit.targets import AbInitio_SMIRNOFF, TorsionProfile_SMIRNOFF
from openff.bespokefit.utils import forcebalance_setup, get_data


class ForceBalanceOptimizer(Optimizer):
    """
    A Optimizer class which controls the interface with ForceBalanace.
    """

    optimizer_name: Literal["ForceBalanceOptimizer"] = "ForceBalanceOptimizer"
    optimizer_description = "A systematic force field optimization tool: https://github.com/leeping/forcebalance"

    # forcebalance settings and validators
    penalty_type: str = "L1"
    job_type: str = "optimize"
    max_iterations: PositiveInt = 10
    convergence_step_criteria: PositiveFloat = 0.01
    convergence_objective_criteria: PositiveFloat = 0.01
    convergence_gradient_criteria: PositiveFloat = 0.01
    n_criteria: PositiveInt = 2
    eig_lowerbound: PositiveFloat = 0.01
    finite_difference_h: PositiveFloat = 0.01
    penalty_additive: PositiveFloat = 1.0
    constrain_charge: bool = False
    initial_trust_radius: float = -0.25
    minimum_trust_radius: float = 0.05
    error_tolerance: PositiveFloat = 1.0
    adaptive_factor: PositiveFloat = 0.2
    adaptive_damping: PositiveFloat = 1.0
    normalize_weights: bool = False
    extras: Dict[str, Any] = {}

    def provenance(self) -> Dict:
        """
        Collect the provenance information for forcebalance.
        """
        import forcebalance

        return {"forcebalance": forcebalance.__version__}

    @classmethod
    def is_available(cls) -> bool:
        try:
            import forcebalance

            return True
        except ImportError:
            return False

    def optimize(self, schema: OptimizationSchema) -> OptimizationSchema:
        """
        This is the main optimization method, which will consume a Workflow stage composed of targets and molecules it will prep them all for fitting
        optimize collect the results and return the completed task.

        Parameters
        ----------
        schema: OptimizationSchema
            The workflow schema that should be executed, which contains the targets ready for fitting.
        """
        # check that the correct optimizer workflow has been supplied
        priors = {}
        fitting_targets = {}
        print("starting OPT")
        if schema.optimizer_name.lower() == self.optimizer_name.lower():
            print("making new fb folders in", os.getcwd())
            # this will set up the file structure and return use back to the current working dir after
            print("new folder name", schema.job_id)
            with forcebalance_setup(schema.job_id):
                # now for each target we need to prep the folders
                fitting_file = os.getcwd()
                print("running opt in ", fitting_file)
                os.chdir("targets")
                for target in schema.targets:
                    target_class = self.get_optimization_target(
                        target_name=target.target_name, **target.settings
                    )
                    self.set_optimization_target(target_class)
                    for param_target in schema.target_parameters:
                        name, value = param_target.get_prior()
                        priors[name] = value

                    print("prepping target class ", target.target_name)
                    target_class.prep_for_fitting(target)
                    # add the entry to the fitting target
                    for task in target.tasks:
                        fitting_targets.setdefault(target_class.name, []).append(
                            task.name
                        )

                os.chdir(fitting_file)
                ff = schema.get_fitting_forcefield()
                ff.to_file(
                    os.path.join("forcefield", "bespoke.offxml"),
                    discard_cosmetic_attributes=False,
                )
                # now make the optimize in file
                self.generate_optimize_in(
                    priors=priors, fitting_targets=fitting_targets
                )
                # now lets execute forcebalanace to fit the molecule
                with open("log.txt", "w") as log:
                    subprocess.run(
                        "ForceBalance optimize.in", shell=True, stdout=log, stderr=log
                    )

                result_workflow = self.collect_results(schema=schema)
        print("OPT finished in folder", os.getcwd())
        return result_workflow

    def collect_results(self, schema: OptimizationSchema) -> OptimizationSchema:
        """
        Collect the results of a forcebalance optimization.

        Check the exit state of the optimization before attempting to update the final smirks parameters.

        Parameters
        ----------
        schema: OptimizationSchema
            The workflow schema that should be updated with the results of the current optimization.

        Returns
        -------
        OptimizationSchema
            The updated workflow schema.
        """
        import copy

        # look for the result
        result = self.read_output()
        schema.status = result["status"]
        ff = ForceFieldEditor(result["forcefield"])
        # make a new list as smirks are updated in place
        final_smirks = copy.deepcopy(schema.target_smirks)
        ff.update_smirks_parameters(smirks=final_smirks)
        # put the new smirks back in the schema
        schema.final_smirks = final_smirks
        return schema

    def read_output(self) -> Dict[str, str]:
        """
        Read the output file of the forcebalance job to determine the exit state of the fitting and the name of the optimized forcefield.

        Returns
        -------
        Dict[str, str]
            A dictionary containing the exit status of the optimization and the file path to the optimized forcefield.
        """
        result = {}
        with open("optimize.out") as log:
            for line in log.readlines():
                if "optimization converged" in line.lower():
                    # optimization finished correctly
                    result["status"] = Status.Complete
                    break
                elif "convergence failure" in line.lower():
                    # did not converge
                    result["status"] = Status.ConvergenceError
                    break
            else:
                # still running?
                result["status"] = Status.Optimizing

        # now we need the path to optimised forcefield
        forcefield_dir = os.path.join("result", "optimize")
        result["forcefield"] = os.path.join(forcefield_dir, "bespoke.offxml")
        return result

    def generate_optimize_in(
        self, priors: Dict[str, float], fitting_targets: Dict[str, List[str]]
    ) -> None:
        """
        Using jinja generate an optimize.in control file for forcebalance at the given location.

        Parameters
        ----------
        priors: Dict[str, float]
            A dictionary containing the prior names and values.
        fitting_targets: Dict[str, List[str]]
            A dictionary containing the fitting target names sorted by forcebalance target.

        Notes
        -----
            This function can be used to generate many optimize in files so many force balance jobs can be ran simultaneously.
        """
        # check that all of the fitting targets have been set
        target_names = [target.name.lower() for target in self.optimization_targets]
        for target_name in fitting_targets.keys():
            if target_name.lower() not in target_names:
                raise TargetNotSetError(
                    f"The target {target_name} is not setup for this optimizer and is required, please add it with runtime options using `set_optimization_target`."
                )

        # grab the template file
        template_file = get_data(os.path.join("templates", "optimize.txt"))
        with open(template_file) as file:
            template = Template(file.read())

        data = self.dict()
        # function to collect the priors from the targets.
        data["priors"] = priors
        # now we need to collect the fitting target data from the schema
        data["fitting_targets"] = fitting_targets
        rendered_template = template.render(**data)

        with open("optimize.in", "w") as opt_in:
            opt_in.write(rendered_template)


# register all of the available targets.
ForceBalanceOptimizer.register_target(AbInitio_SMIRNOFF())
ForceBalanceOptimizer.register_target(TorsionProfile_SMIRNOFF())
