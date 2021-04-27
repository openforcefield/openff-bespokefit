import itertools
import json
import os
from typing import List, Tuple

import numpy as np
import pytest
from openff.toolkit.topology import Molecule
from qcportal.models import OptimizationRecord, ResultRecord, TorsionDriveRecord

from openff.bespokefit.optimizers.forcebalance.factories import (
    AbInitioTargetFactory,
    ForceBalanceInputFactory,
    OptGeoTargetFactory,
    TorsionProfileTargetFactory,
    VibrationTargetFactory,
)
from openff.bespokefit.schema.fitting import OptimizationSchema
from openff.bespokefit.schema.targets import (
    AbInitioTargetSchema,
    OptGeoTargetSchema,
    TorsionProfileTargetSchema,
    VibrationTargetSchema,
)
from openff.bespokefit.utilities import temporary_cd


def read_qdata(qdata_file: str) -> Tuple[List[np.array], List[float], List[np.array]]:
    """
    Read a torsiondrive and forcebalance qdata files and return the geometry energy and gradients.

    Parameters
    ----------
    qdata_file: str
        The file path to the torsiondrive and forcebalance qdata files.
    """

    coords, energies, gradients = [], [], []
    with open(qdata_file) as qdata:
        for line in qdata.readlines():
            if "COORDS" in line:
                geom = np.array(line.split()[1:])
                energies.append(geom)
            elif "ENERGY" in line:
                energies.append(float(line.split()[-1]))
            elif "GRADIENT" in line:
                grad = np.array(line.split()[1:])
                gradients.append(grad)

    return coords, energies, gradients


@pytest.mark.parametrize("with_gradients", [False, True])
def test_generate_ab_initio_target(
    qc_torsion_drive_record: Tuple[TorsionDriveRecord, Molecule], with_gradients
):

    with temporary_cd():

        AbInitioTargetFactory._generate_target(
            AbInitioTargetSchema(), [qc_torsion_drive_record]
        )

        assert os.path.isfile("scan.xyz")
        assert os.path.isfile("input.sdf")
        assert os.path.isfile("conf.pdb")
        assert os.path.isfile("metadata.json")
        assert os.path.isfile("qdata.txt")

        # make sure the pdb order was not changed
        original_molecule = Molecule.from_file("input.sdf")
        pdb_molecule = Molecule.from_file("conf.pdb")

        isomorphic, atom_map = Molecule.are_isomorphic(
            original_molecule, pdb_molecule, return_atom_map=True
        )
        assert isomorphic is True
        assert atom_map == dict((i, i) for i in range(original_molecule.n_atoms))

        # make sure the scan coords and energies match
        coords, energies, gradients = read_qdata(qdata_file="qdata.txt")

        # if with_gradients:
        #     # make sure gradients were written
        #     coords, energies, gradients = read_qdata(qdata_file=qdata_file)
        #     reference_data = target_schema.tasks[0].reference_data()
        #     for i, (coord, energy, gradient) in enumerate(
        #             zip(coords, energies, gradients)):
        #         # find the reference data
        #         data = reference_data[i]
        #         assert data.energy == energy
        #         assert coord == data.molecule.geometry.flatten().tolist()
        #         assert gradient == data.gradient.flatten().tolist()
        #
        # else:
        #     # make sure no gradients were written
        #     assert not gradients
        #
        #     reference_data = qc_torsion_drive_record.get_final_energies()
        #
        #     for i, (coord, energy) in enumerate(zip(coords, energies)):
        #         # find the reference data
        #         data = reference_data[i]
        #         assert data.energy == energy
        #         assert coord == data.molecule.geometry.flatten().tolist()


def test_generate_torsion_target(
    qc_torsion_drive_record: Tuple[TorsionDriveRecord, Molecule]
):

    with temporary_cd():

        TorsionProfileTargetFactory._generate_target(
            TorsionProfileTargetSchema(), [qc_torsion_drive_record]
        )

        assert os.path.isfile("scan.xyz")
        assert os.path.isfile("input.sdf")
        assert os.path.isfile("conf.pdb")
        assert os.path.isfile("metadata.json")
        assert os.path.isfile("qdata.txt")

        # make sure the pdb order was not changed
        original_molecule = Molecule.from_file("input.sdf")
        pdb_molecule = Molecule.from_file("conf.pdb")

        isomorphic, atom_map = Molecule.are_isomorphic(
            original_molecule, pdb_molecule, return_atom_map=True
        )
        assert isomorphic is True
        assert atom_map == dict((i, i) for i in range(original_molecule.n_atoms))

        with open("metadata.json") as file:
            metadata = json.load(file)

        assert "torsion_grid_ids" in metadata
        assert "energy_decrease_thresh" in metadata
        assert "energy_upper_limit" in metadata


def test_generate_optimization_target(
    qc_optimization_record: Tuple[OptimizationRecord, Molecule]
):

    with temporary_cd():

        OptGeoTargetFactory._generate_target(
            OptGeoTargetSchema(),
            [
                qc_optimization_record,
                qc_optimization_record,
            ],
        )

        for (index, extension) in itertools.product([0, 1], ["xyz", "sdf", "pdb"]):
            assert os.path.isfile(f"{qc_optimization_record[0].id}-{index}.{extension}")

        assert os.path.isfile("optget_options.txt")


def test_opt_geo_batching(qc_optimization_record: ResultRecord):

    qc_records = [qc_optimization_record] * 120

    target_batches = OptGeoTargetFactory._batch_qc_records(
        OptGeoTargetSchema(), qc_records
    )

    assert len(target_batches) == 3

    assert len(target_batches["opt-geo-batch-0"]) == 50
    assert len(target_batches["opt-geo-batch-1"]) == 50
    assert len(target_batches["opt-geo-batch-2"]) == 20


def test_generate_vibration_target(qc_hessian_record: Tuple[ResultRecord, Molecule]):
    with temporary_cd():

        VibrationTargetFactory._generate_target(
            VibrationTargetSchema(), [qc_hessian_record]
        )

        assert os.path.isfile("vdata.txt")
        assert os.path.isfile("input.sdf")
        assert os.path.isfile("conf.pdb")


def test_force_balance_factory(tmpdir, general_optimization_schema: OptimizationSchema):

    ForceBalanceInputFactory.generate(tmpdir, general_optimization_schema)
