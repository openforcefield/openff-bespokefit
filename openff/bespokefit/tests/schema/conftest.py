import copy
import os

import pytest
from openff.qcsubmit.results import TorsionDriveCollectionResult
from openff.toolkit.topology import Molecule
from simtk import unit

from openff.bespokefit.schema.bespoke.tasks import TorsionTask
from openff.bespokefit.schema.data import BespokeQCData
from openff.bespokefit.utilities import get_data_file_path, get_molecule_cmiles


@pytest.fixture()
def ethane_torsion_task():

    occo_molecule: Molecule = Molecule.from_file(
        file_path=get_data_file_path(
            os.path.join("test", "qc-datasets", "occo", "occo.sdf")
        ),
        file_format="sdf",
    )

    entry = TorsionTask(
        name="occo",
        fragment=False,
        input_conformers=[occo_molecule.conformers[0].value_in_unit(unit.angstrom)],
        attributes=get_molecule_cmiles(occo_molecule),
        dihedrals=[(2, 0, 1, 3)],
    )

    return entry


@pytest.fixture()
def collected_ethane_torsion_task(ethane_torsion_task):

    entry = copy.deepcopy(ethane_torsion_task)

    # load up the ethane result
    result = TorsionDriveCollectionResult.parse_file(
        get_data_file_path(os.path.join("test", "qc-datasets", "occo", "occo.json"))
    )

    entry.update_with_results(results=list(result.collection.values())[0])

    return entry


@pytest.fixture()
def ethane_bespoke_data(ethane_torsion_task):
    return BespokeQCData(tasks=[ethane_torsion_task])
