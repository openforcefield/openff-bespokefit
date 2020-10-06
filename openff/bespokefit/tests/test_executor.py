"""
Tests for the executor class which runs and error cycles and optimizations.
"""

import pytest
from openforcefield.topology import Molecule
from qcsubmit.results import TorsionDriveCollectionResult
from qcsubmit.testing import temp_directory

from ..executor import Executor
from ..schema.fitting import FittingSchema
from ..utils import get_data
from .schema.test_fitting import get_fitting_schema


def test_executor_no_collection():
    """
    Test using the executor when there are no tasks to collect only optimizations to run.
    """
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    # now make the schema
    schema = get_fitting_schema(molecules=ethane)
    result = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
    schema.update_with_results(results=result)

    # now submit to the executor
    execute = Executor(fitting_schema=schema)
    # there are no collection tasks
    assert execute.task_map == {}
    # there is one fitting task
    assert execute.total_tasks == 1
    # submit the optimization
    with temp_directory():
        execute.execute()
        # stop the server processes
        execute.server.stop()
        # make sure they are all finished
        assert execute.total_tasks == 0
        # check the results have been saved
        smirks = execute.fitting_schema.molecules[0].workflow[0].target_smirks
        # make sure they have been updated
        for smirk in smirks:
            for term in smirk.terms.values():
                assert float(term.k.split()[0]) != 1e-5

        # now round load up the results
        schema = FittingSchema.parse_file("final_results.json")
        # make sure all tasks are complete
        assert schema.molecules[0].get_next_optimization_stage() is None


def test_executor_basic_collection():
    """
    Test using the executor to run a ethane torsion scan.
    """
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")
    # now make the schema
    schema = get_fitting_schema(molecules=ethane)

    # this will run an ani2x torsion scan
    execute = Executor(fitting_schema=schema)
    assert execute.total_tasks == 1
    assert len(execute.task_map) == 1
    with temp_directory():
        execute.execute()
        execute.server.stop()
        # now we should have completed the scan and the optimization
        # check the results have been saved
        smirks = execute.fitting_schema.molecules[0].workflow[0].target_smirks
        # make sure they have been updated
        for smirk in smirks:
            for term in smirk.terms.values():
                assert float(term.k.split()[0]) != 1e-5

        # now round load up the results
        schema = FittingSchema.parse_file("final_results.json")
        # make sure all tasks are complete
        assert schema.molecules[0].get_next_optimization_stage() is None
        assert execute.fitting_schema.molecules[0].workflow[0].targets[0].entries[0].get_reference_data() is not None
