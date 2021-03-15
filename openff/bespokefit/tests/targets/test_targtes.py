"""
Test specific target classes like torsions.
"""

import os
from typing import Union

import pytest
from openff.qcsubmit.results import TorsionDriveCollectionResult
from openff.qcsubmit.testing import temp_directory
from openforcefield.topology import Molecule

from openff.bespokefit.exceptions import MissingReferenceError
from openff.bespokefit.schema import TargetSchema
from openff.bespokefit.targets import AbInitio_SMIRNOFF, TorsionProfile_SMIRNOFF
from openff.bespokefit.utils import get_data, get_molecule_cmiles, read_qdata


def biphenyl_target(target: Union[AbInitio_SMIRNOFF, TorsionProfile_SMIRNOFF]) -> TargetSchema:
    """
    Return a target schema made by the target class for biphenyl.
    """
    mol = Molecule.from_file(file_path=get_data("biphenyl.sdf"), file_format="sdf")
    target_schema = target.generate_target_schema()
    # create one task schema
    task_schema = target.generate_fitting_task(molecule=mol, fragment=False, attributes=get_molecule_cmiles(molecule=mol), dihedrals=[(5, 9, 10, 6), ])
    target_schema.add_fitting_task(task=task_schema)
    return target_schema


def test_prep_for_fitting_no_ref():
    """
    Make sure an error is raised if we try to fit with missing reference data.
    """
    torsion_target = AbInitio_SMIRNOFF()
    target_schema = biphenyl_target(target=torsion_target)

    with pytest.raises(MissingReferenceError):
        torsion_target.prep_for_fitting(fitting_target=target_schema)


def test_abinitio_fitting_prep_no_gradient():
    """
    Test preparing for fitting using the abinitio target.
    """

    torsion_target = AbInitio_SMIRNOFF()
    torsion_target.fit_gradient = False
    target_schema = biphenyl_target(target=torsion_target)
    biphenyl = Molecule.from_file(file_path=get_data("biphenyl.sdf"), file_format="sdf")
    # now load in a scan result we have saved
    result_data = TorsionDriveCollectionResult.parse_file(get_data("biphenyl.json.xz"))
    # now try and update the results
    target_schema.update_with_results(results=result_data)
    assert target_schema.ready_for_fitting is True
    # now try and prep for fitting
    with temp_directory():
        torsion_target.prep_for_fitting(fitting_target=target_schema)
        # we should only have one torsion drive to do here
        folders = os.listdir(".")
        assert len(folders) == 1
        target_files = os.listdir(folders[0])
        assert "molecule.pdb" in target_files
        assert "scan.xyz" in target_files
        assert "molecule.mol2" in target_files
        assert "qdata.txt" in target_files
        # now we need to make sure the pdb order was not changed
        mol = Molecule.from_file(os.path.join(folders[0], "molecule.pdb"), file_format="pdb")
        isomorphic, atom_map = Molecule.are_isomorphic(biphenyl, mol, return_atom_map=True)
        assert isomorphic is True
        assert atom_map == dict((i, i) for i in range(biphenyl.n_atoms))

        # also make sure charges are in the mol2 file
        mol = Molecule.from_file(os.path.join(folders[0], "molecule.mol2"), "mol2")
        assert mol.partial_charges is not None

        # make sure the scan coords and energies match
        qdata_file = os.path.join(folders[0], "qdata.txt")
        coords, energies, gradients = read_qdata(qdata_file=qdata_file)
        # make sure no gradients were written
        assert not gradients
        reference_data = target_schema.tasks[0].reference_data()
        for i, (coord, energy) in enumerate(zip(coords, energies)):
            # find the reference data
            data = reference_data[i]
            assert data.energy == energy
            assert coord == data.molecule.geometry.flatten().tolist()


def test_abinitio_fitting_prep_gradient():
    """
    Test prepearing for fitting and using the gradient.
    """

    torsion_target = AbInitio_SMIRNOFF()
    torsion_target.fit_gradient = True
    target_schema = biphenyl_target(target=torsion_target)
    biphenyl = Molecule.from_file(file_path=get_data("biphenyl.sdf"), file_format="sdf")
    # now load in a scan result we have saved
    result_data = TorsionDriveCollectionResult.parse_file(get_data("biphenyl.json.xz"))
    # now try and update the results
    target_schema.update_with_results(results=result_data)
    assert target_schema.ready_for_fitting is True
    # now try and prep for fitting
    with temp_directory():
        torsion_target.prep_for_fitting(fitting_target=target_schema)
        # we should only have one torsion drive to do here
        folders = os.listdir(".")
        assert len(folders) == 1
        target_files = os.listdir(folders[0])
        assert "molecule.pdb" in target_files
        assert "scan.xyz" in target_files
        assert "molecule.mol2" in target_files
        assert "qdata.txt" in target_files
        # now we need to make sure the pdb order was not changed
        mol = Molecule.from_file(os.path.join(folders[0], "molecule.pdb"), file_format="pdb")
        isomorphic, atom_map = Molecule.are_isomorphic(biphenyl, mol, return_atom_map=True)
        assert isomorphic is True
        assert atom_map == dict((i, i) for i in range(biphenyl.n_atoms))

        # also make sure charges are in the mol2 file
        mol = Molecule.from_file(os.path.join(folders[0], "molecule.mol2"), "mol2")
        assert mol.partial_charges is not None

        # make sure the scan coords and energies match
        qdata_file = os.path.join(folders[0], "qdata.txt")
        coords, energies, gradients = read_qdata(qdata_file=qdata_file)
        reference_data = target_schema.tasks[0].reference_data()
        for i, (coord, energy, gradient) in enumerate(zip(coords, energies, gradients)):
            # find the reference data
            data = reference_data[i]
            assert data.energy == energy
            assert coord == data.molecule.geometry.flatten().tolist()
            assert gradient == data.gradient.flatten().tolist()


def test_torsionprofile_metadata():
    """
    Make sure that when using the torsionprofile target we make the metatdat.json file.
    """
    from openff.qcsubmit.serializers import deserialize
    torsion_target = TorsionProfile_SMIRNOFF()
    target_schema = biphenyl_target(target=torsion_target)
    # now load in a scan result we have saved
    result_data = TorsionDriveCollectionResult.parse_file(get_data("biphenyl.json.xz"))
    # now try and update the results
    target_schema.update_with_results(results=result_data)
    assert target_schema.ready_for_fitting is True
    # now try and prep for fitting
    with temp_directory():
        torsion_target.prep_for_fitting(fitting_target=target_schema)
        # we should only have one torsion drive to do here
        folders = os.listdir(".")
        assert len(folders) == 1
        target_files = os.listdir(folders[0])
        assert "molecule.pdb" in target_files
        assert "scan.xyz" in target_files
        assert "molecule.mol2" in target_files
        assert "qdata.txt" in target_files
        assert "metadata.json" in target_files

        metadata = deserialize(file_name=os.path.join(folders[0], "metadata.json"))
        # now make sure the json is complete
        entry = target_schema.tasks[0]
        assert entry.dihedrals[0] == tuple(metadata["dihedrals"][0])
        for data in entry.reference_data():
            assert data.extras["dihedral_angle"] in metadata["torsion_grid_ids"]
