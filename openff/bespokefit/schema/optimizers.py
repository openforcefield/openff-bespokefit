import abc
from typing import Dict, Union

from pydantic import Field, PositiveFloat, PositiveInt
from typing_extensions import Literal

from openff.bespokefit.utilities.pydantic import SchemaBase


class BaseOptimizerSchema(SchemaBase, abc.ABC):
    """The base class for a model which stores the settings of an optimization engine."""

    type: Literal["base"] = "base"

    max_iterations: PositiveInt = Field(
        10, description="The maximum number of optimization iterations to perform."
    )


class ForceBalanceSchema(BaseOptimizerSchema, abc.ABC):
    """A class containing the main ForceBalance optimizer settings to use during an
    optimization.

    Priors and target definitions are stored separately as part of an
    ``OptimizationSchema``.
    """

    type: Literal["ForceBalance"] = "ForceBalance"

    penalty_type: Literal["L1", "L2"] = Field("L2", description="The penalty type.")

    step_convergence_threshold: PositiveFloat = Field(
        0.01, description="The step size convergence criterion."
    )
    objective_convergence_threshold: PositiveFloat = Field(
        0.01, description="The objective function convergence criterion."
    )
    gradient_convergence_threshold: PositiveFloat = Field(
        0.01, description="The gradient norm convergence criterion."
    )

    n_criteria: PositiveInt = Field(
        2,
        description="The number of convergence thresholds that must be met for "
        "convergence.",
    )

    eigenvalue_lower_bound: PositiveFloat = Field(
        0.01,
        description="The minimum eigenvalue for applying steepest descent correction.",
    )

    finite_difference_h: PositiveFloat = Field(
        0.01,
        description="The step size for finite difference derivatives in many functions.",
    )

    penalty_additive: PositiveFloat = Field(
        1.0,
        description="The factor for the multiplicative penalty function in the "
        "objective function.",
    )

    initial_trust_radius: float = Field(
        -0.25,
        description="The initial value of the optimizers adaptive trust radius which "
        "'adapts' (i.e. increases or decreases) based on whether the last step was a "
        "good or bad step.",
    )
    minimum_trust_radius: float = Field(
        0.05, description="The minimum value of the optimizers adaptive trust radius."
    )

    error_tolerance: PositiveFloat = Field(
        1.0,
        description="Steps that increase the objective function by more than this "
        "will be rejected.",
    )

    adaptive_factor: PositiveFloat = Field(
        0.2,
        description="The amount to change the step size by in the event of a good / "
        "bad step.",
    )
    adaptive_damping: PositiveFloat = Field(
        1.0, description="A damping factor that restraints the trust radius to trust0."
    )

    normalize_weights: bool = Field(
        False, description="Whether to normalize the weights for the fitting targets"
    )

    extras: Dict[str, str] = Field(
        {},
        description="Extra settings (mostly logging settings) to include in the "
        "ForceBalance input file.",
    )


OptimizerSchema = Union[ForceBalanceSchema]
