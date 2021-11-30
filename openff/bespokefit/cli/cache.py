import click
import redis
import rich
from click_option_group import optgroup
from rich import pretty
from typing import Optional
from typing import Union

from openff.bespokefit.cli.utilities import create_command, print_header
from openff.bespokefit.executor.utilities.redis import is_redis_available, launch_redis
from openff.qcsubmit.results import TorsionDriveResultCollection, OptimizationResultCollection

@click.group("cache")
def cache_cli():
    #TODO do we want the redius database to be saved in a standard location as it is directory dependent?
    """Commands to manually update the qc data cache."""



def update_from_qcsubmit_options(
        result_file: str,
        launch_redis_if_unavailable: Optional[bool] = True,
):
    return [
        optgroup("Input Configuration"),
        optgroup.option()
    ]


def update():
    """
    The main worker function which updates the redis cache with qcsubmit results objects.
    """
    # first download qcsubmit results
    # connect to / launch redis
    # save and close
    # have options for files and address as they all go through the same in fastructure should they be mutally exclusive?

    pass


def _update_from_qcsubmit_result(qcsubmit_results: Union[TorsionDriveResultCollection, OptimizationResultCollection], redis_connection: redis.Redis):
    """Update the qcgeneration redis cache using qcsubmit results objects."""
    # take the results and convert them to tasks and store in redis if not present
    pass


