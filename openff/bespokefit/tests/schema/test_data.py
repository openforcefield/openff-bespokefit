import os

from openff.qcsubmit.datasets import TorsiondriveDataset, TorsionDriveEntry
from openff.qcsubmit.results import TorsionDriveCollectionResult

from openff.bespokefit.schema.data import BespokeQCData
from openff.bespokefit.utilities import get_data_file_path


def test_bespoke_data_tasks_validator(ethane_torsion_task):

    ethane_torsion_task.name = "fake-name"

    bespoke_data = BespokeQCData(tasks=[ethane_torsion_task])

    assert len(bespoke_data.tasks) == 1
    assert bespoke_data.tasks[0].name == "torsion1d-0"


def test_bespoke_data_not_ready_for_fit(ethane_bespoke_data):
    assert not ethane_bespoke_data.ready_for_fitting


def test_bespoke_data_ready_for_fit(collected_ethane_torsion_task):

    bespoke_data = BespokeQCData(tasks=[collected_ethane_torsion_task])
    assert bespoke_data.ready_for_fitting


def test_get_qcsubmit_tasks(ethane_bespoke_data):

    qc_tasks = ethane_bespoke_data.get_qcsubmit_tasks()

    assert len(qc_tasks) == 1
    assert isinstance(qc_tasks[0], TorsionDriveEntry)


def test_build_qcsubmit_dataset(ethane_torsion_task):

    bespoke_data = BespokeQCData()
    assert bespoke_data.build_qcsubmit_dataset() is None

    bespoke_data.tasks = [ethane_torsion_task]

    qc_data_set = bespoke_data.build_qcsubmit_dataset()
    assert isinstance(qc_data_set, TorsiondriveDataset)

    assert qc_data_set.n_records == 1


def test_update_with_results(ethane_torsion_task):

    # load up the ethane result
    result = TorsionDriveCollectionResult.parse_file(
        get_data_file_path(os.path.join("test", "qc-datasets", "occo", "occo.json"))
    )

    ethane_torsion_task.update_with_results(results=list(result.collection.values())[0])

    reference_data = ethane_torsion_task.reference_data()

    assert reference_data is not None
    assert len(reference_data) == 24


def test_get_task_map(ethane_bespoke_data):

    task_map = ethane_bespoke_data.get_task_map()
    assert len(task_map) == 1
