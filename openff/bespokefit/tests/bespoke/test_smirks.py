"""
Test the smirks generator.
"""
import os
from typing import List, Tuple

import pytest
from openff.toolkit.topology import Molecule
from openff.utilities import get_data_file_path

from openff.bespokefit.bespoke.smirks import SmirksGenerator
from openff.bespokefit.exceptions import SMIRKSTypeError
from openff.bespokefit.schema.smirnoff import SmirksType
from openff.bespokefit.utilities.smirnoff import ForceFieldEditor


def all_covered(matches, molecule) -> bool:
    """
    Make sure all parameter types are covered by the matches list.
    """
    # check atoms
    for i in range(molecule.n_atoms):
        assert (i,) in matches
    # check bonds
    for bond in molecule.bonds:
        bond = (bond.atom1_index, bond.atom2_index)
        assert bond in matches or tuple(reversed(bond)) in matches
    # check angles
    for angle in molecule.angles:
        angle = tuple([atom.molecule_atom_index for atom in angle])
        assert angle in matches or tuple(reversed(angle)) in matches
    # check torsions
    for torsion in molecule.propers:
        dihedral = tuple([atom.molecule_atom_index for atom in torsion])
        assert dihedral in matches or tuple(reversed(dihedral)) in matches

    return True


def condense_matches(matches: List[Tuple[int, ...]]) -> List[Tuple[int, ...]]:
    """
    For a set of chemical environment matches condense them to a unique list of matches
    taking into account matches that appear forwards or backwards.
    """
    new_matches = []
    for match in matches:
        if match not in new_matches and tuple(reversed(match)) not in new_matches:
            new_matches.append(match)
    return new_matches


def compare_matches(matches, target) -> bool:
    """
    Make sure the matches and target matches are the same.
    """

    for match in target:
        if match not in matches and tuple(reversed(match)) not in matches:
            return False
    return True


def test_bespoke_atom_smirks():
    """
    Make sure we can generate bespoke atom smirks for a molecule and that they cover the
    correct atoms, also check all atoms have a bespoke smirks.
    """
    gen = SmirksGenerator(target_smirks=[SmirksType.Vdw])
    mol = Molecule.from_smiles("C")

    atom_smirks = gen.generate_smirks_from_molecules(molecule=mol)
    # there should only be 2 unique smirks
    assert len(atom_smirks) == 2
    # make sure the correct atoms are hit
    all_atoms = []
    for smirk in atom_smirks:
        atoms = condense_matches(mol.chemical_environment_matches(smirk.smirks))
        all_atoms.extend(atoms)
        assert set(atoms) == smirk.atoms
    # make sure all atoms have a bespoke smirks
    for i in range(mol.n_atoms):
        assert (i,) in all_atoms


def test_bespoke_bond_smirks():
    """
    Make sure we can generate a bespoke bond smirks for each bond in a molecule and that
    every bond is covered.
    """
    gen = SmirksGenerator(target_smirks=[SmirksType.Bonds])
    mol = Molecule.from_smiles("CC")

    bond_smirks = gen.generate_smirks_from_molecules(molecule=mol)
    # there should be 2 unique bond smirks
    assert len(bond_smirks) == 2
    all_bonds = []
    for smirk in bond_smirks:
        atoms = condense_matches(mol.chemical_environment_matches(smirk.smirks))
        all_bonds.extend(atoms)
        assert set(atoms) == smirk.atoms
    # make sure all bonds are covered
    for bond in mol.bonds:
        assert (bond.atom1_index, bond.atom2_index) in all_bonds


def test_bespoke_angle_smirks():
    """
    Make sure we can generate a bespoke angle smirks for each angle, also make sure the
    intended atoms are covered and that every angle has a bespoke smirks.
    """
    gen = SmirksGenerator(target_smirks=[SmirksType.Angles])
    mol = Molecule.from_smiles("CC")

    angle_smirks = gen.generate_smirks_from_molecules(molecule=mol)
    # there should be 2 unique smirks
    assert len(angle_smirks) == 2
    all_angles = []
    for smirk in angle_smirks:
        atoms = condense_matches(mol.chemical_environment_matches(smirk.smirks))
        all_angles.extend(atoms)
        assert set(atoms) == smirk.atoms
    # make sure all angles are covered
    for angle in mol.angles:
        assert tuple([atom.molecule_atom_index for atom in angle]) in all_angles


def test_bespoke_target_torsion_smirks():
    """
    Generate bespoke torsion smirks only for the target torsions and make sure the
    intended atoms are covered.
    """
    gen = SmirksGenerator(target_smirks=[SmirksType.ProperTorsions])
    mol = Molecule.from_file(
        get_data_file_path(
            os.path.join("test", "molecules", "OCCO.sdf"), "openff.bespokefit"
        )
    )

    torsion_smirks = gen.generate_smirks_from_molecules(
        molecule=mol, central_bond=(1, 2)
    )
    # there should be 3 unique smirks for this molecule
    # H-C-C-H, H-C-C-O, O-C-C-O
    assert len(torsion_smirks) == 3
    for smirk in torsion_smirks:
        atoms = condense_matches(mol.chemical_environment_matches(smirk.smirks))
        assert compare_matches(atoms, smirk.atoms) is True


def test_bespoke_torsion_smirks():
    """
    Generate bespoke smirks for every torsion in the molecule, make sure that the
    intended atoms are covered and make sure every torsion has a bespoke smirks.
    """
    gen = SmirksGenerator(target_smirks=[SmirksType.ProperTorsions])
    mol = Molecule.from_file(
        get_data_file_path(
            os.path.join("test", "molecules", "OCCO.sdf"), "openff.bespokefit"
        )
    )

    torsion_smirks = gen.generate_smirks_from_molecules(molecule=mol)
    # there should be 5 unique torsions
    assert len(torsion_smirks) == 5

    all_torsions = []
    for smirk in torsion_smirks:
        atoms = condense_matches(mol.chemical_environment_matches(smirk.smirks))
        all_torsions.extend(atoms)
        assert compare_matches(atoms, smirk.atoms) is True

    for torsion in mol.propers:
        dihedral = tuple([atom.molecule_atom_index for atom in torsion])
        assert dihedral in all_torsions or tuple(reversed(dihedral)) in all_torsions


def test_get_all_bespoke_smirks_molecule():
    """
    Generate bespoke smirks for all parameters in a molecule, make sure they all hit the
    intended atoms, and every term is now bespoke.
    """
    gen = SmirksGenerator()
    gen.target_smirks = [
        SmirksType.Vdw,
        SmirksType.Bonds,
        SmirksType.Angles,
        SmirksType.ProperTorsions,
    ]

    mol = Molecule.from_smiles("CO")

    all_bespoke_smirks = gen.generate_smirks_from_molecules(
        molecule=mol,
    )
    # this is a list of all bespoke smirks with real initial values
    all_matches = []
    for smirk in all_bespoke_smirks:
        atoms = condense_matches(mol.chemical_environment_matches(smirk.smirks))
        assert compare_matches(atoms, smirk.atoms) is True
        all_matches.extend(atoms)

    assert all_covered(all_matches, mol) is True


def test_get_all_bespoke_smirks_fragment(bace_fragment_data):
    """
    Generate bespoke smirks for all parameters using cluster graphs so the smirks apply to both parent and fragment.
    """
    gen = SmirksGenerator()
    gen.target_smirks = [
        SmirksType.Vdw,
        SmirksType.Bonds,
        SmirksType.Angles,
        SmirksType.ProperTorsions,
    ]
    all_bespoke_smirks = gen.generate_smirks_from_fragments(
        fragment_data=bace_fragment_data
    )
    all_matches = []
    for smirk in all_bespoke_smirks:
        atoms = condense_matches(
            bace_fragment_data.fragment_molecule.chemical_environment_matches(
                smirk.smirks
            )
        )
        assert compare_matches(atoms, smirk.atoms) is True
        all_matches.extend(atoms)


def test_get_all_smirks():
    """
    Get the full list of smirks which cover this molecule from the forcefield, no new
    smirks should be generated here.
    """
    gen = SmirksGenerator()
    gen.target_smirks = [
        SmirksType.Vdw,
        SmirksType.Bonds,
        SmirksType.Angles,
        SmirksType.ProperTorsions,
    ]

    mol = Molecule.from_smiles("CO")

    all_smirks = gen._get_all_smirks(
        molecule=mol,
        force_field_editor=ForceFieldEditor("openff_unconstrained-1.3.0.offxml"),
    )
    # this is a list of all of the smirks from the forcefield
    all_matches = []
    for smirk in all_smirks:
        atoms = condense_matches(mol.chemical_environment_matches(smirk.smirks))
        assert compare_matches(atoms, smirk.atoms) is True
        all_matches.extend(atoms)

    assert all_covered(all_matches, mol) is True


def test_no_smirks_requested():
    """
    Make sure an error is raised if we try and generate smirks but do not request any
    smirks types.
    """
    gen = SmirksGenerator()
    gen.target_smirks = []

    mol = Molecule.from_smiles("CC")

    with pytest.raises(SMIRKSTypeError):
        gen.generate_smirks_from_molecules(molecule=mol)


@pytest.mark.parametrize(
    "bespoke_smirks",
    [
        pytest.param(True, id="Generate bespoke terms"),
        pytest.param(False, id="Standard terms"),
    ],
)
def test_generate_smirks(bespoke_smirks):
    """
    Test the main worker method to gather bespoke and non bespoke terms.
    """
    gen = SmirksGenerator()
    gen.target_smirks = [
        SmirksType.Vdw,
    ]
    gen.generate_bespoke_terms = bespoke_smirks

    mol = Molecule.from_smiles("CC")
    smirks_list = gen.generate_smirks_from_molecules(molecule=mol)

    # we only request one parameter type
    types = set([smirk.type for smirk in smirks_list])
    assert len(types) == 1


@pytest.mark.parametrize(
    "bespoke_smirks",
    [
        pytest.param(True, id="Generate bespoke terms"),
        pytest.param(False, id="Standard terms"),
    ],
)
@pytest.mark.parametrize(
    "expand_torsions",
    [
        pytest.param(True, id="Expand torsions"),
        pytest.param(False, id="Normal torsions"),
    ],
)
def test_expand_torsion_terms(bespoke_smirks, expand_torsions):
    """
    Make sure torsion terms are expanded up to 4 when requested for bespoke and standard
    smirks.
    """
    gen = SmirksGenerator()
    gen.target_smirks = [
        SmirksType.ProperTorsions,
    ]
    gen.generate_bespoke_terms = bespoke_smirks
    gen.expand_torsion_terms = expand_torsions

    mol = Molecule.from_smiles("CC")

    smirks_list = gen.generate_smirks_from_molecules(molecule=mol)
    # make sure there is only one parameter type
    types = set([smirk.type for smirk in smirks_list])
    assert len(types) == 1
    for smirk in smirks_list:
        if expand_torsions:
            assert len(smirk.terms) == 4
        else:
            assert len(smirk.terms) < 4
