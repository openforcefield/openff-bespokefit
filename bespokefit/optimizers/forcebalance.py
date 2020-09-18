import os
import re
import subprocess
from typing import Any, Dict, List

from jinja2 import Template
from pydantic import PositiveFloat, PositiveInt

from ..common_structures import Status
from ..forcefield_tools import ForceFieldEditor
from ..schema.fitting import WorkflowSchema
from ..targets import AbInitio_SMIRNOFF, TorsionProfile_SMIRNOFF
from ..utils import forcebalance_setup, get_data
from .model import Optimizer


class ForceBalanceOptimizer(Optimizer):
    """
    A Optimizer class which controls the interface with ForceBalanace.
    """

    optimizer_name = "ForceBalanceOptimizer"
    optimizer_description = "A systematic force field optimization tool: https://github.com/leeping/forcebalance"

    # forcebalance settings and validators
    penalty_type: str = "L2"
    job_type: str = "optimize"
    max_iterations: PositiveInt = 100
    convergence_step_criteria: PositiveFloat = 0.01
    convergence_objective_criteria: PositiveFloat = 0.01
    convergence_gradient_criteria: PositiveFloat = 0.01
    n_criteria: PositiveInt = 2
    eig_lowerbound: PositiveFloat = 0.01
    finite_difference_h: PositiveFloat = 0.01
    penalty_additive: PositiveFloat = 1.0
    constrain_charge: bool = False
    initial_trust_radius: float = 0.25
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

    def optimize(
        self, workflow: WorkflowSchema, initial_forcefield: str
    ) -> WorkflowSchema:
        """
        This is the main optimization method, which will consume a Workflow stage composed of targets and molecules it will prep them all for fitting
        optimize collect the results and return the completed task.

        Parameters:
            workflow: The workflow schema that should be executed, which contains the targets ready for fitting.
            initial_forcefield: The name of the initial force field to be used as the optimization starting point.
        """
        # check that the correct optimizer workflow has been supplied
        priors = {}
        fitting_targets = {}
        if workflow.optimizer_name == self.optimizer_name:
            # this will set up the file structure and return use back to the current working dir after
            with forcebalance_setup(workflow.job_id):
                # now for each target we need to prep the folders
                fitting_file = os.getcwd()
                os.chdir("targets")
                for target in workflow.targets:
                    target_class = self.get_optimization_target(
                        target_name=target.target_name, **target.provenance
                    )
                    self.set_optimization_target(target_class)
                    for param_target in target_class.parameter_targets:
                        name, value = param_target.get_prior()
                        priors[name] = value
                        target_class.prep_for_fitting(target)
                        # add the entry to the fitting target
                        for entry in target.entries:
                            fitting_targets.setdefault(target_class.name, []).append(
                                entry.name
                            )

                os.chdir(fitting_file)
                ff = workflow.get_fitting_forcefield(initial_forcefield)
                ff.to_file(os.path.join("forcefield", "bespoke.offxml"))
                # now make the optimize in file
                self.generate_optimize_in(
                    priors=priors, fitting_targets=fitting_targets
                )
                # now lets execute forcebalanace to fit the molecule
                with open("log.txt", "w") as log:
                    subprocess.run(
                        "ForceBalance optimize.in", shell=True, stdout=log, stderr=log
                    )

                return self.collect_results(workflow=workflow)

    def collect_results(self, workflow: WorkflowSchema) -> WorkflowSchema:
        """
        Collect the results of a forcebalance optimization.

        Check the exit state of the optimization before attempting to update the final smirks parameters.

        Parameters
        ----------
        workflow: WorkflowSchema
            The workflow schema that should be updated with the results of the current optimization.

        Returns
        -------
        WorkflowSchema
            The updated workflow schema.
        """
        # look for the result
        result = self.read_output()
        if result["status"] == Status.Complete:
            workflow.status = Status.Complete
            ff = ForceFieldEditor(result["forcefield"])
            # update the smirks in place
            ff.update_smirks_parameters(smirks=workflow.target_smirks)
        else:
            workflow.status = Status.Error

        return workflow

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
                    result["status"] = Status.Error
                    break
            else:
                # still running?
                result["status"] = Status.Optimizing

        # now we need the path to the last forcefield file
        forcefield_dir = os.path.join("result", "optimize")
        files = os.listdir(forcefield_dir)
        files.remove("bespoke.offxml")
        forcefields = [
            (int(re.search("[0-9]+", file_name).group()), file_name)
            for file_name in files
        ]
        # now sort them so the highest optimization is the last in the list
        forcefields.sort(key=lambda x: x[0])
        result["forcefield"] = os.path.join(forcefield_dir, forcefields[-1][-1])
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

        Note:
            This function can be used to generate many optimize in files so many force balance jobs can be ran simultaneously.
        """

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
