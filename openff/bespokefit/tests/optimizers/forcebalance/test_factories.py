import itertools
import json
import os

from qcportal.models import ResultRecord, TorsionDriveRecord

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


def test_generate_ab_initio_target(qc_torsion_drive_record: TorsionDriveRecord):

    with temporary_cd():

        AbInitioTargetFactory._generate_target(
            AbInitioTargetSchema(),
            [qc_torsion_drive_record]
        )

        assert os.path.isfile("scan.xyz")
        assert os.path.isfile("input.sdf")
        assert os.path.isfile("conf.pdb")
        assert os.path.isfile("metadata.json")
        assert os.path.isfile("qdata.txt")


def test_generate_torsion_target(qc_torsion_drive_record: TorsionDriveRecord):

    with temporary_cd():

        TorsionProfileTargetFactory._generate_target(
            TorsionProfileTargetSchema(),
            [qc_torsion_drive_record]
        )

        assert os.path.isfile("scan.xyz")
        assert os.path.isfile("input.sdf")
        assert os.path.isfile("conf.pdb")
        assert os.path.isfile("metadata.json")
        assert os.path.isfile("qdata.txt")

        with open("metadata.json") as file:
            metadata = json.load(file)

        assert "torsion_grid_ids" in metadata
        assert "energy_decrease_thresh" in metadata
        assert "energy_upper_limit" in metadata


def test_generate_optimization_target(qc_optimization_record: ResultRecord):

    with temporary_cd():

        OptGeoTargetFactory._generate_target(
            OptGeoTargetSchema(),
            [
                qc_optimization_record,
                qc_optimization_record,
            ]
        )

        for (index, extension) in itertools.product([0, 1], ["xyz", "sdf", "pdb"]):
            assert os.path.isfile(f"{qc_optimization_record.id}-{index}.{extension}")

        assert os.path.isfile("optget_options.txt")


def test_generate_vibration_target(qc_hessian_record: ResultRecord):
    with temporary_cd():

        VibrationTargetFactory._generate_target(
            VibrationTargetSchema(), [qc_hessian_record]
        )

        assert os.path.isfile("vdata.txt")
        assert os.path.isfile("input.sdf")
        assert os.path.isfile("conf.pdb")


def test_force_balance_factory(
    tmpdir, general_optimization_schema: OptimizationSchema
):

    ForceBalanceInputFactory.generate(tmpdir, general_optimization_schema)
