"""
Test specific target classes like torsions.
"""

import os

import pytest
from openforcefield.topology import Molecule

from qcsubmit.results import TorsionDriveCollectionResult
from qcsubmit.testing import temp_directory

from ...exceptions import MissingReferenceError
from ...schema.smirks import TorsionSmirks
from ...targets import AbInitio_SMIRNOFF, TorsionDrive1D, TorsionProfile_SMIRNOFF
from ...targets.atom_selection import TorsionSelection
from ...utils import get_data, read_qdata


def test_get_all_torsions():
    """
    Test finding all possible torsions which pass through a single central bond.
    """
    ethane = Molecule.from_file(get_data("ethane.sdf"), file_format="sdf")
    torsion_target = TorsionDrive1D()
    all_torsions = torsion_target.get_all_torsions(bond=(0, 1), molecule=ethane)
    assert len(all_torsions) == 9


@pytest.mark.parametrize("molecule_data", [
    pytest.param(("CO", TorsionSelection.All, 1), id="Ethanol all bonds"),
    pytest.param(("CC", TorsionSelection.All, 1), id="Ethane all bonds"),
    pytest.param(("CO", TorsionSelection.NonTerminal, 0), id="Ethanol non terminal"),
    pytest.param(("CN(CC12C3CC(CC31)C2(F)F)C(C)(C)C", TorsionSelection.All, 7), id="Many bonds all"),
    pytest.param(("CN(CC12C3CC(CC31)C2(F)F)C(C)(C)C", TorsionSelection.NonTerminal, 3), id="Many bonds non termianl"),

])
def test_select_rotatable_bonds(molecule_data):
    """
    Test finding all rotatable bonds in a molecule for a combination of torsion selection methods.
    """
    molecule_smiles, torsion_selection, no_tors = molecule_data
    mol = Molecule.from_smiles(smiles=molecule_smiles, allow_undefined_stereo=True)
    torsion_target = TorsionDrive1D(torsion_selection=torsion_selection)
    assert len(torsion_target.select_rotatable_bonds(molecule=mol)) == no_tors


def test_torsiondrive_provenance():
    """
    Make sure that the torsiondrive provenance included fragmenter and chemper.
    """
    torsion_target = TorsionDrive1D(fragmentation=True)
    data = torsion_target.provenance()
    assert "chemper" in data
    assert "openeye" in data
    assert "rdkit" in data
    assert "fragmenter" in data

    # now turn of the fragmentation
    torsion_target.fragmentation = False
    data = torsion_target.provenance()
    assert "fragmenter" not in data


def test_torsiondrive_fragmentation_success():
    """
    Make sure that fragmentation is handled correctly when we make a fitting schema when fragmentation is possible.
    """
    # bace can be fragmented into 3 parts 2 of which are the same
    bace = Molecule.from_file(file_path=get_data("bace.sdf"), file_format="sdf")
    torsion_target = TorsionDrive1D(fragmentation=True)
    fragment_data = torsion_target._fragment_molecule(off_molecule=bace)
    assert len(fragment_data) == 3

    fragments = [fragment.fragment_molecule for fragment in fragment_data]
    # make sure the fragments are correct
    for fragment in ["bace_frag1.sdf", "bace_frag2.sdf"]:
        frag_mol = Molecule.from_file(file_path=get_data(fragment), file_format="sdf")
        assert frag_mol in fragments

    # make sure all of the central bonds are different
    torsions = set([fragment.fragment_torsion for fragment in fragment_data])
    assert len(torsions) == 3


def test_torsiondrive_fragmentation_fail():
    """
    Test torsiondrive fragmentation when fragmenter can not make a fragment.
    """

    mol = Molecule.from_smiles(smiles="BrCO")
    torsion_target = TorsionDrive1D(fragmentation=True)
    fragment_data = torsion_target._fragment_molecule(off_molecule=mol)
    assert len(fragment_data) == 1
    assert fragment_data[0].fragment_molecule == mol
    assert fragment_data[0].fragment_parent_mapping == dict((i, i) for i in range(mol.n_atoms))


def test_torsiondrive_fragmentation_same_molecule():
    """
    Test that making a new parameters still works when the parent is given as a fragment.
    """
    mol = Molecule.from_smiles(smiles="OCCO")
    torsion_target = TorsionDrive1D(fragmentation=True)
    fragment_data = torsion_target._fragment_molecule(off_molecule=mol)
    assert len(fragment_data) == 1


def test_generate_fitting_schema_fragmentation():
    """
    Test make a torsion fitting schema for a molecule.
    """

    torsion_target = TorsionDrive1D(fragmentation=True)
    bace = Molecule.from_file(file_path=get_data("bace.sdf"), file_format="sdf")

    # the toolkit will try and produce this many conformers
    schema = torsion_target.generate_fitting_schema(molecule=bace, conformers=4)
    assert torsion_target.name == schema.target_name
    assert torsion_target.dict() == schema.provenance
    assert len(schema.entries) == 3
    assert schema.ready_for_fitting is False
    for entry in schema.entries:
        assert len(entry.input_conformers) <= 4


@pytest.mark.parametrize("fragmentation", [
    pytest.param(True, id="With Fragmentation"),
    pytest.param(False, id="Without Fragmentation")
])
def test_generate_fitting_schema_same_molecule(fragmentation):
    """
    Test making a torsion fitting schema with and without fragmentation parent molecule is always returned.
    """
    torsion_target = TorsionDrive1D(fragmentation=fragmentation)
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")

    schema = torsion_target.generate_fitting_schema(molecule=ethane, conformers=4)
    assert torsion_target.name == schema.target_name
    assert torsion_target.dict() == schema.provenance
    assert len(schema.entries) == 1
    # there should only be one type of smirks found due to symmetry
    smirks = schema.get_target_smirks()
    assert len(smirks) == 1
    assert isinstance(smirks[0], TorsionSmirks) is True


def test_torsion_target_available():
    """
    Make sure that the fitting environments correctly have all packages installed.
    """
    assert TorsionDrive1D.is_available() is True


def test_prep_for_fitting_no_ref():
    """
    Make sure an error is raised if we try to fit with missing reference data.
    """
    torsion_target = AbInitio_SMIRNOFF(fragmentation=False)
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")

    schema = torsion_target.generate_fitting_schema(molecule=ethane)

    with pytest.raises(MissingReferenceError):
        torsion_target.prep_for_fitting(fitting_target=schema)


def test_abinitio_fitting_prep_no_gradient():
    """
    Test preparing for fitting using the abinitio target.
    """

    torsion_target = AbInitio_SMIRNOFF(fragmentation=False)
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")

    schema = torsion_target.generate_fitting_schema(molecule=ethane)
    # now load in a scan result we have saved
    result_data = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
    # now try and update the results
    schema.update_with_results(results=[result_data, ])
    assert schema.ready_for_fitting is True
    # now try and prep for fitting
    with temp_directory():
        torsion_target.prep_for_fitting(fitting_target=schema)
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
        isomorphic, atom_map = Molecule.are_isomorphic(ethane, mol, return_atom_map=True)
        assert isomorphic is True
        assert atom_map == dict((i, i) for i in range(ethane.n_atoms))

        # also make sure charges are in the mol2 file
        mol = Molecule.from_file(os.path.join(folders[0], "molecule.mol2"), "mol2")
        assert mol.partial_charges is not None

        # make sure the scan coords and energies match
        qdata_file = os.path.join(folders[0], "qdata.txt")
        coords, energies, gradients = read_qdata(qdata_file=qdata_file)
        # make sure no gradients were written
        assert not gradients
        reference_data = schema.entries[0].reference_data
        for i, (coord, energy) in enumerate(zip(coords, energies)):
            # find the reference data
            data = reference_data[i]
            assert data.energy == energy
            assert coord == data.molecule.geometry.flatten().tolist()


def test_abinitio_fitting_prep_gradient():
    """
    Test prepearing for fitting and using the gradient.
    """

    torsion_target = AbInitio_SMIRNOFF(fragmentation=False, fit_gradient=True)
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")

    schema = torsion_target.generate_fitting_schema(molecule=ethane)
    # now load in a scan result we have saved
    result_data = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
    # now try and update the results
    schema.update_with_results(results=[result_data, ])
    assert schema.ready_for_fitting is True
    # now try and prep for fitting
    with temp_directory():
        torsion_target.prep_for_fitting(fitting_target=schema)
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
        isomorphic, atom_map = Molecule.are_isomorphic(ethane, mol, return_atom_map=True)
        assert isomorphic is True
        assert atom_map == dict((i, i) for i in range(ethane.n_atoms))

        # also make sure charges are in the mol2 file
        mol = Molecule.from_file(os.path.join(folders[0], "molecule.mol2"), "mol2")
        assert mol.partial_charges is not None

        # make sure the scan coords and energies match
        qdata_file = os.path.join(folders[0], "qdata.txt")
        coords, energies, gradients = read_qdata(qdata_file=qdata_file)
        reference_data = schema.entries[0].reference_data
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
    from qcsubmit.serializers import deserialize
    torsion_target = TorsionProfile_SMIRNOFF(fragmentation=False)
    ethane = Molecule.from_file(file_path=get_data("ethane.sdf"), file_format="sdf")

    schema = torsion_target.generate_fitting_schema(molecule=ethane)
    assert schema.target_name == torsion_target.name
    assert schema.provenance == torsion_target.dict()

    # now load in a scan result we have saved
    result_data = TorsionDriveCollectionResult.parse_file(get_data("ethane.json"))
    # now try and update the results
    schema.update_with_results(results=[result_data, ])
    assert schema.ready_for_fitting is True
    # now try and prep for fitting
    with temp_directory():
        torsion_target.prep_for_fitting(fitting_target=schema)
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
        entry = schema.entries[0]
        assert entry.extras["dihedrals"][0] == tuple(metadata["dihedrals"][0])
        for data in entry.reference_data:
            assert data.extras["dihedral_angle"] in metadata["torsion_grid_ids"]
