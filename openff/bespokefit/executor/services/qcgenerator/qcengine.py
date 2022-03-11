from qcengine.procedures.torsiondrive import TorsionDriveProcedure
from qcengine.procedures import register_procedure
from multiprocessing import Pool


class TorsionDriveProcedureParallel(TorsionDriveProcedure):
    """
    Override the _spawn_optimizations method of the basic torsiondrive procedure to allow for parallel optimizations
    within one worker.
    """

    _defaults = {"name": "TorsionDriveParallel", "procedure": "torsiondrive"}

    def _spawn_optimizations(self):
        """
        Spawn parallel optimizations based on the number of next jobs and available workers.
        """

        pass


# register for local usage
register_procedure(TorsionDriveProcedureParallel())
