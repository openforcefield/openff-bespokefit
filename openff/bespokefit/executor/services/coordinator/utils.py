"""Utilities for coordinator service."""
import hashlib
from typing import Optional

import redis
from openff.toolkit.typing.engines.smirnoff import ForceField
from openff.toolkit.utils.exceptions import ParameterLookupError

from openff.bespokefit.schema.fitting import BespokeOptimizationSchema
from openff.bespokefit.schema.results import BespokeOptimizationResults


def _hash_fitting_schema(fitting_schema: BespokeOptimizationSchema) -> str:
    """
    Create a hash based on the whole fitting schema for any optimised parameters.
    """
    hash_string = (
        fitting_schema.smirk_settings.json() + fitting_schema.initial_force_field_hash
    )
    for stage in fitting_schema.stages:
        # drop the reference data form each target and the parameters from each stage
        hash_string += stage.json(
            exclude={"targets": {"__all__": {"reference_data"}}, "parameters": ...},
        )
    hash_string = hashlib.sha512(hash_string.encode()).hexdigest()
    return hash_string


def get_cached_parameters(
    fitting_schema: BespokeOptimizationSchema,
    redis_connection: redis.Redis,
) -> Optional[ForceField]:
    """
    For the given fitting schema create a hash and check for a cached force field which contains a set of fit torsion parameters.
    """
    hash_string = _hash_fitting_schema(fitting_schema=fitting_schema)

    cached_ff = redis_connection.get(hash_string)
    if cached_ff is not None:
        return ForceField(cached_ff, allow_cosmetic_attributes=True)
    return None


def cache_parameters(
    results_schema: BespokeOptimizationResults,
    redis_connection: redis.Redis,
) -> str:
    """
    Cache any fitted torsion parameters saved in the final refit force field.

    Returns
    -------
         The string the parameters are cached under

    """
    hash_string = _hash_fitting_schema(fitting_schema=results_schema.input_schema)
    cached_ff = redis_connection.get(hash_string)
    if cached_ff is not None:
        cached_force_field = ForceField(cached_ff)
    else:
        # create a new blank FF
        cached_force_field = ForceField()

    torsion_handler_cache = cached_force_field.get_parameter_handler("ProperTorsions")
    refit_force_field = ForceField(results_schema.refit_force_field)
    refit_torsions = refit_force_field.get_parameter_handler("ProperTorsions")

    for stage in results_schema.input_schema.stages:
        for parameter in stage.parameters:
            try:
                # the parameter maybe be in more than one stage so only save once
                _ = torsion_handler_cache[parameter.smirks]
            except ParameterLookupError:
                # we need to add the parameter to the cache
                torsion_handler_cache.add_parameter(
                    parameter=refit_torsions[parameter.smirks],
                )

    # now set the force field back in the cache
    redis_connection.set(
        hash_string,
        cached_force_field.to_string(discard_cosmetic_attributes=False),
    )
    return hash_string
