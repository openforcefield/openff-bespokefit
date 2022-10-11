import itertools
import json
import os
from typing import List, Tuple

import numpy as np
import pytest
from openff.toolkit.topology import Molecule
from openff.toolkit.typing.engines.smirnoff import ForceField
from openff.utilities import skip_if_missing
from qcelemental.models.procedures import TorsionDriveResult

from openff.bespokefit.optimizers.forcebalance.factories import (
    AbInitioTargetFactory,
    ForceBalanceInputFactory,
    OptGeoTargetFactory,
    TorsionProfileTargetFactory,
    VibrationTargetFactory,
    _TargetFactory,
)
from openff.bespokefit.schema.data import LocalQCData
from openff.bespokefit.schema.fitting import OptimizationSchema
from openff.bespokefit.schema.targets import (
    AbInitioTargetSchema,
    OptGeoTargetSchema,
    TorsionProfileTargetSchema,
    VibrationTargetSchema,
)
from openff.bespokefit.utilities.tempcd import temporary_cd


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


@pytest.mark.parametrize(
    "result_fixture",
    [
        "qc_torsion_drive_qce_result",
        "qc_optimization_qce_result",
        "qc_hessian_qce_result",
    ],
)
def test_local_to_qc_records(result_fixture, request):
    qc_result, expected_molecule = request.getfixturevalue(result_fixture)
    assert expected_molecule.n_conformers >= 1

    [(qc_record, molecule)] = _TargetFactory._local_to_qc_records(
        LocalQCData(qc_records=[qc_result])
    )

    assert type(qc_record) == type(qc_result)

    assert molecule.to_smiles() == expected_molecule.to_smiles()
    assert molecule.n_conformers == expected_molecule.n_conformers

    if isinstance(qc_result, TorsionDriveResult):
        assert (
            molecule.properties["grid_ids"] == expected_molecule.properties["grid_ids"]
        )


@skip_if_missing("openeye.oechem")
@pytest.mark.parametrize(
    "result_fixture", ["qc_torsion_drive_record", "qc_torsion_drive_qce_result"]
)
@pytest.mark.parametrize("with_gradients", [False, True])
def test_generate_ab_initio_target(result_fixture, with_gradients, request):
    qc_torsion_drive_record = request.getfixturevalue(result_fixture)

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


@skip_if_missing("openeye.oechem")
@pytest.mark.parametrize(
    "result_fixture", ["qc_torsion_drive_record", "qc_torsion_drive_qce_result"]
)
def test_generate_torsion_target(result_fixture, request):
    qc_torsion_drive_record = request.getfixturevalue(result_fixture)

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


@pytest.mark.parametrize(
    "result_fixture", ["qc_optimization_record", "qc_optimization_qce_result"]
)
def test_generate_optimization_target(result_fixture, request):
    qc_optimization_record = request.getfixturevalue(result_fixture)

    with temporary_cd():
        OptGeoTargetFactory._generate_target(
            OptGeoTargetSchema(extras={"batch_size": "51"}),
            [
                qc_optimization_record,
                qc_optimization_record,
            ],
        )

        for index, extension in itertools.product([0, 1], ["xyz", "sdf", "pdb"]):
            qc_record_id = (
                qc_optimization_record[0].extras["id"]
                if "id" in qc_optimization_record[0].extras
                else qc_optimization_record[0].id
            )
            assert os.path.isfile(f"{qc_record_id}-{index}.{extension}")

        assert os.path.isfile("optgeo_options.txt")


@pytest.mark.parametrize(
    "result_fixture", ["qc_optimization_record", "qc_optimization_qce_result"]
)
def test_opt_geo_batching(result_fixture, request):
    qc_optimization_record = request.getfixturevalue(result_fixture)
    qc_records = [qc_optimization_record] * 120

    target_batches = OptGeoTargetFactory._batch_qc_records(
        OptGeoTargetSchema(extras={"batch_size": "51"}), qc_records
    )

    assert len(target_batches) == 3

    assert len(target_batches["opt-geo-batch-0"]) == 51
    assert len(target_batches["opt-geo-batch-1"]) == 51
    assert len(target_batches["opt-geo-batch-2"]) == 18


def test_opt_geo_target_section():
    target_schema = OptGeoTargetSchema(extras={"batch_size": "51"})

    target_section = OptGeoTargetFactory._generate_targets_section(
        target_schema, ["target-1"]
    )

    assert "batch_size" not in target_section
    assert "batch_size" in target_schema.extras


@pytest.mark.parametrize(
    "result_fixture", ["qc_hessian_record", "qc_hessian_qce_result"]
)
def test_generate_vibration_target(result_fixture, request):
    qc_hessian_record = request.getfixturevalue(result_fixture)

    with temporary_cd():
        VibrationTargetFactory._generate_target(
            VibrationTargetSchema(), [qc_hessian_record]
        )

        assert os.path.isfile("vdata.txt")
        assert os.path.isfile("input.sdf")
        assert os.path.isfile("conf.pdb")


def test_force_balance_factory(tmpdir, general_optimization_schema: OptimizationSchema):
    ForceBalanceInputFactory.generate(
        tmpdir,
        general_optimization_schema.stages[0],
        ForceField(general_optimization_schema.initial_force_field),
    )


def test_get_fitting_force_field(general_optimization_schema, tmpdir):
    with temporary_cd(str(tmpdir)):
        ForceBalanceInputFactory._generate_force_field_directory(
            general_optimization_schema.stages[0],
            ForceField(general_optimization_schema.initial_force_field),
        )

        expected_path = os.path.join("forcefield", "force-field.offxml")
        assert os.path.isfile(expected_path)

        force_field = ForceField(expected_path, allow_cosmetic_attributes=True)

    target_parameter = general_optimization_schema.stages[0].parameters[0]

    parameter_handler = force_field.get_parameter_handler(target_parameter.type)
    parameter = parameter_handler.parameters[target_parameter.smirks]

    assert parameter.attribute_is_cosmetic("parameterize")
    assert parameter._parameterize == "k1"
