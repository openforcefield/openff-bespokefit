import os
from collections import defaultdict

import pytest
from openff.fragmenter.utils import get_atom_index
from openff.toolkit.topology import Molecule
from openff.toolkit.typing.engines.smirnoff import (
    ForceField,
    ProperTorsionHandler,
    vdWHandler,
)
from openff.units import unit
from openff.utilities import get_data_file_path

from openff.bespokefit._tests import does_not_raise
from openff.bespokefit.exceptions import SMIRKSTypeError
from openff.bespokefit.schema.smirnoff import validate_smirks
from openff.bespokefit.utilities.smirks import (
    SMIRKSGenerator,
    compare_smirks_graphs,
    get_cached_torsion_parameters,
)
from openff.bespokefit.utilities.smirnoff import ForceFieldEditor, SMIRKSType


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


def condense_matches(matches: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
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


def test_get_cached_torsion_no_match(bace):
    """
    Make sure no parameter is returned if no cached parameter matches the same atoms as the bespoke parameter.
    """
    bespoke_parameter = ProperTorsionHandler.ProperTorsionType(
        smirks="[*:1]-[#6:2]-[*:3]-[*:4]",
        periodicity=[1],
        phase=[0 * unit.degree],
        k=[1 * unit.kilocalories_per_mole],
    )
    force_field = ForceField("openff_unconstrained-1.0.0.offxml")
    cached_parameter = get_cached_torsion_parameters(
        molecule=bace,
        bespoke_parameter=bespoke_parameter,
        cached_parameters=force_field.get_parameter_handler(
            "ProperTorsions",
        ).parameters,
    )
    assert cached_parameter is None


def test_get_cached_torsion(bace):
    """
    Make sure we can correctly identify a parameter which is a valid cached term.
    """
    bespoke_parameter = ProperTorsionHandler.ProperTorsionType(
        smirks="[#6H1:1]@[#6:2]-!@[#6:3]@[#6H1:4]",
        periodicity=[1],
        phase=[0 * unit.degree],
        k=[1 * unit.kilocalories_per_mole],
    )
    force_field = ForceField("openff_unconstrained-1.0.0.offxml")
    cached_parameter = get_cached_torsion_parameters(
        molecule=bace,
        bespoke_parameter=bespoke_parameter,
        cached_parameters=force_field.get_parameter_handler(
            "ProperTorsions",
        ).parameters,
    )
    assert cached_parameter is not None
    assert "cached" in cached_parameter._cosmetic_attribs
    # make sure the k value is updated
    assert cached_parameter.k[0] == unit.Quantity(
        0.9155269008137,
        unit.kilocalories_per_mole,
    )
    # make sure the smirks has not changed
    assert cached_parameter.smirks == "[#6H1:1]@[#6:2]-!@[#6:3]@[#6H1:4]"


@pytest.mark.parametrize(
    "smirks1, smirks2, expected",
    [
        ("[#6:1]-[#6:2]", "[#6:1]-[#6:2]", True),
        ("[#6:1]-[#6:2]", "[#6:1]-[#1:2]", False),
    ],
)
def test_compare_smirks_graphs(smirks1, smirks2, expected):
    assert compare_smirks_graphs(smirks1, smirks2) == expected


@pytest.mark.parametrize(
    "smirks, n_tags, expected_raises",
    [
        ("[#6:1]", 1, does_not_raise()),
        ("[#6:1]-[#6:2]", 1, pytest.raises(AssertionError)),
    ],
)
def test_validate_smirks(smirks, n_tags, expected_raises):
    with expected_raises:
        validate_smirks(smirks, n_tags)


@pytest.mark.parametrize(
    "mol, smirks_type, n_expected, expected_lambda, central_bond",
    [
        ("C", SMIRKSType.Vdw, 2, lambda mol: {(i,) for i in range(mol.n_atoms)}, None),
        (
            "CC",
            SMIRKSType.Bonds,
            2,
            lambda mol: {(bond.atom1_index, bond.atom2_index) for bond in mol.bonds},
            None,
        ),
        (
            "CC",
            SMIRKSType.Angles,
            2,
            lambda mol: {
                tuple(atom.molecule_atom_index for atom in angle)
                for angle in mol.angles
            },
            None,
        ),
        (
            Molecule.from_file(
                get_data_file_path(
                    os.path.join("test", "molecules", "OCCO.sdf"),
                    "openff.bespokefit",
                ),
            ),
            SMIRKSType.ProperTorsions,
            5,
            lambda mol: {
                tuple(atom.molecule_atom_index for atom in torsion)
                for torsion in mol.propers
            },
            None,
        ),
        (
            Molecule.from_file(
                get_data_file_path(
                    os.path.join("test", "molecules", "OCCO.sdf"),
                    "openff.bespokefit",
                ),
            ),
            SMIRKSType.ProperTorsions,
            3,
            lambda mol: {
                tuple(atom.molecule_atom_index for atom in torsion)
                for torsion in mol.propers
                if torsion[1].atomic_number == 6 and torsion[2].atomic_number == 6
            },
            (1, 2),
        ),
    ],
)
def test_bespoke_smirks(mol, smirks_type, n_expected, expected_lambda, central_bond):
    """
    Make sure we can generate bespoke atom smirks for a molecule and that they cover the
    correct atoms, also check all atoms have a bespoke smirks.
    """
    gen = SMIRKSGenerator(target_smirks=[smirks_type])

    if isinstance(mol, str):
        mol = Molecule.from_smiles(mol)

    generated_parameters = gen.generate_smirks_from_molecule(
        molecule=mol,
        central_bond=central_bond,
    )
    assert len(generated_parameters) == n_expected

    all_matches = [
        match
        for parameter in generated_parameters
        for match in condense_matches(
            mol.chemical_environment_matches(parameter.smirks),
        )
    ]

    assert len({*all_matches}) == len(all_matches)
    assert compare_matches({*all_matches}, expected_lambda(mol))


def test_get_all_bespoke_smirks_molecule():
    """
    Generate bespoke smirks for all parameters in a molecule, make sure they all hit the
    intended atoms, and every term is now bespoke.
    """
    gen = SMIRKSGenerator()
    gen.target_smirks = [
        SMIRKSType.Vdw,
        SMIRKSType.Bonds,
        SMIRKSType.Angles,
        SMIRKSType.ProperTorsions,
    ]

    mol = Molecule.from_smiles("CO")

    bespoke_parameters = gen.generate_smirks_from_molecule(
        molecule=mol,
    )
    # this is a list of all bespoke smirks with real initial values
    all_matches = []
    for parameter in bespoke_parameters:
        atoms = condense_matches(mol.chemical_environment_matches(parameter.smirks))
        all_matches.extend(atoms)

    assert all_covered(all_matches, mol) is True


def test_get_all_bespoke_smirks_fragment(bace_fragment_data):
    """Generate bespoke smirks for all parameters using cluster graphs so the smirks
    apply to both parent and fragment.
    """

    fragment = bace_fragment_data.fragments[0]
    fragment_molecule = fragment.molecule

    parent_molecule = bace_fragment_data.parent_molecule

    gen = SMIRKSGenerator()
    gen.target_smirks = [
        SMIRKSType.Vdw,
        SMIRKSType.ProperTorsions,
    ]

    bespoke_parameters = gen.generate_smirks_from_fragment(
        parent=bace_fragment_data.parent_molecule,
        fragment=bace_fragment_data.fragments[0].molecule,
        fragment_map_indices=bace_fragment_data.fragments[0].bond_indices,
    )
    matches_by_type = defaultdict(list)

    for parameter in bespoke_parameters:
        parent_matches = parent_molecule.chemical_environment_matches(parameter.smirks)
        assert len(parent_matches) > 0

        fragment_matches = condense_matches(
            bace_fragment_data.fragments[0].molecule.chemical_environment_matches(
                parameter.smirks,
            ),
        )
        matches_by_type[parameter.__class__].extend(fragment_matches)

    assert all(
        sorted(match[1:3])
        == sorted(get_atom_index(fragment_molecule, i) for i in fragment.bond_indices)
        for match in matches_by_type[ProperTorsionHandler.ProperTorsionType]
    )
    assert sorted(matches_by_type[vdWHandler.vdWType]) == [
        (i,) for i in range(fragment_molecule.n_atoms)
    ]


def test_get_existing_parameters():
    """
    Get the full list of smirks which cover this molecule from the forcefield, no new
    smirks should be generated here.
    """
    gen = SMIRKSGenerator()

    gen.target_smirks = [
        SMIRKSType.Vdw,
        SMIRKSType.Bonds,
        SMIRKSType.Angles,
        SMIRKSType.ProperTorsions,
    ]

    mol = Molecule.from_smiles("CO")

    all_smirks = gen._get_existing_parameters(
        molecule=mol,
        force_field_editor=ForceFieldEditor("openff_unconstrained-1.3.0.offxml"),
    )
    # this is a list of all of the smirks from the forcefield
    all_matches = []

    for smirk in all_smirks:
        atoms = condense_matches(mol.chemical_environment_matches(smirk.smirks))
        all_matches.extend(atoms)

    assert all_covered(all_matches, mol) is True


def test_no_smirks_requested():
    """
    Make sure an error is raised if we try and generate smirks but do not request any
    smirks types.
    """
    gen = SMIRKSGenerator()
    gen.target_smirks = []

    mol = Molecule.from_smiles("CC")

    with pytest.raises(SMIRKSTypeError):
        gen.generate_smirks_from_molecule(molecule=mol)


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
    gen = SMIRKSGenerator()
    gen.target_smirks = [SMIRKSType.Vdw]
    gen.generate_bespoke_terms = bespoke_smirks

    mol = Molecule.from_smiles("CC")
    parameters = gen.generate_smirks_from_molecule(molecule=mol)

    # we only request one parameter type
    types = {type(parameter) for parameter in parameters}
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
    gen = SMIRKSGenerator()
    gen.target_smirks = [
        SMIRKSType.ProperTorsions,
    ]
    gen.generate_bespoke_terms = bespoke_smirks
    gen.expand_torsion_terms = expand_torsions

    mol = Molecule.from_smiles("CC")

    parameters = gen.generate_smirks_from_molecule(molecule=mol)

    # make sure there is only one parameter type
    parameter_types = {parameter.__class__ for parameter in parameters}
    assert len(parameter_types) == 1

    for parameter in parameters:
        if expand_torsions:
            assert len(parameter.k) == 4
            assert parameter.periodicity == [1, 2, 3, 4]
        else:
            assert len(parameter.k) < 4
        if bespoke_smirks:
            assert "-BF" in parameter.id


def test_fit_interpolated_torsion():
    """
    Make sure an error is raised if we try and fit an interpolated torsion.
    """
    ff = ForceFieldEditor(force_field="openff_unconstrained-1.3.0.offxml")
    # add an interploated general parameter
    parameter = ff.force_field["ProperTorsions"].parameters[0]
    parameter._k_bondorder = [1, 2]
    ff.force_field["ProperTorsions"]._parameters = [parameter]
    # run the generation
    gen = SMIRKSGenerator(initial_force_field=ff)
    mol = Molecule.from_smiles("CC")
    with pytest.raises(NotImplementedError):
        _ = gen.generate_smirks_from_molecule(molecule=mol)
