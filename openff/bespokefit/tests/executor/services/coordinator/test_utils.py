from openff.toolkit.typing.engines.smirnoff import ForceField

from openff.bespokefit.executor.services.coordinator.utils import (
    _hash_fitting_schema,
    cache_parameters,
    get_cached_parameters,
)
from openff.bespokefit.schema.smirnoff import ProperTorsionSMIRKS


def test_hash_fitting_schema(ptp1b_input_schema_single):
    """
    Test hashing a fitting schema for caching.
    """
    normal_hash = _hash_fitting_schema(fitting_schema=ptp1b_input_schema_single)
    # add a parameter to fit and rehash, should not change the hash
    ptp1b_input_schema_single.stages[0].parameters.append(
        ProperTorsionSMIRKS(smirks="[*:1]-[#6:2]-[#6:3]-[*:4]", attributes={"k1"})
    )
    assert normal_hash == _hash_fitting_schema(fitting_schema=ptp1b_input_schema_single)

    # now change a setting and rehash, this should change the hash
    ptp1b_input_schema_single.smirk_settings.expand_torsion_terms = False
    assert normal_hash != _hash_fitting_schema(fitting_schema=ptp1b_input_schema_single)


def test_get_cached_parameters(redis_connection, ptp1b_input_schema_single):
    """
    Test querying redis for cached parameters
    """

    # try and get some parameters from redis after not storing
    force_field = get_cached_parameters(
        fitting_schema=ptp1b_input_schema_single, redis_connection=redis_connection
    )
    assert force_field is None
    # now store some parameters under this hash
    openff_ff = ForceField("openff-1.0.0.offxml")
    redis_connection.set(
        _hash_fitting_schema(ptp1b_input_schema_single), openff_ff.to_string()
    )

    cached_ff = get_cached_parameters(
        fitting_schema=ptp1b_input_schema_single, redis_connection=redis_connection
    )

    assert cached_ff.__hash__() == openff_ff.__hash__()


def test_cache_parameters(bespoke_optimization_results, redis_connection):
    """
    Test adding fitted parameters to a redis cache.
    """
    # create a blank cache for the forcefield
    hash_string = cache_parameters(
        results_schema=bespoke_optimization_results, redis_connection=redis_connection
    )
    force_field = ForceField(redis_connection.get(hash_string))
    # we should have nothing saved.
    assert len(force_field.get_parameter_handler("ProperTorsions").parameters) == 0
    # add a mock parameter to signify it has been fit and cache again
    bespoke_optimization_results.input_schema.stages[0].parameters.append(
        ProperTorsionSMIRKS(smirks="[*:1]~[#6X3:2]-[#6X3:3]~[*:4]", attributes={"k1"})
    )
    cache_parameters(
        results_schema=bespoke_optimization_results, redis_connection=redis_connection
    )
    # grab the force field again and make sure we have a parameter saved
    force_field = ForceField(redis_connection.get(hash_string))
    # we should have nothing saved.
    assert len(force_field.get_parameter_handler("ProperTorsions").parameters) == 1
