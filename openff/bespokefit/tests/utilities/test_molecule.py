import pytest
from openff.toolkit.topology import Molecule

from openff.bespokefit.utilities.molecule import (
    _oe_get_atom_symmetries,
    _rd_get_atom_symmetries,
    get_atom_symmetries,
    get_torsion_indices,
    group_valence_by_symmetry,
)


@pytest.mark.parametrize(
    "get_symmetries",
    [_oe_get_atom_symmetries, _rd_get_atom_symmetries, get_atom_symmetries],
)
def test_get_atom_symmetries(get_symmetries):

    molecule = Molecule.from_mapped_smiles("[H:1][C:2]([H:3])([H:4])[O:5][H:6]")

    try:
        atom_symmetries = get_symmetries(molecule)

    except ModuleNotFoundError as e:

        pytest.skip(f"missing optional dependency - {e.name}")
        return

    assert len({atom_symmetries[i] for i in (0, 2, 3)}) == 1
    assert len({atom_symmetries[i] for i in (1, 4, 5)}) == 3


@pytest.mark.parametrize(
    "valence_terms, expected_values",
    [
        (
            [(0,), (1,), (2,), (3,), (4,), (5,)],
            [[(0,), (2,), (3,)], [(1,)], [(4,)], [(5,)]],
        ),
        (
            [(1, 0), (1, 2), (1, 3), (1, 4), (4, 5)],
            [[(1, 0), (1, 2), (1, 3)], [(1, 4)], [(4, 5)]],
        ),
    ],
)
def test_group_by_symmetry(valence_terms, expected_values):

    molecule = Molecule.from_mapped_smiles("[H:1][C:2]([H:3])([H:4])[O:5][H:6]")

    valence_groups = group_valence_by_symmetry(molecule, valence_terms)
    assert len(valence_groups) == len(expected_values)

    actual_values = [*valence_groups.values()]

    assert sorted(actual_values) == sorted(expected_values)


@pytest.mark.parametrize(
    "smiles, central_bond, expected_values",
    [
        (
            "[H:1][C:2]([H:3])=[C:4]([H:5])[H:6]",
            None,
            [(0, 1, 3, 4), (0, 1, 3, 5), (2, 1, 3, 4), (2, 1, 3, 5)],
        ),
        (
            "[H:1][C:2]([H:3])=[C:4]([H:5])[H:6]",
            (1, 3),
            [(0, 1, 3, 4), (0, 1, 3, 5), (2, 1, 3, 4), (2, 1, 3, 5)],
        ),
        (
            "[H:1][C:2]([H:3])=[C:4]=[C:5]([H:6])[H:7]",
            (1, 3),
            [(0, 1, 3, 4), (2, 1, 3, 4)],
        ),
    ],
)
def test_get_torsion_indices(smiles, central_bond, expected_values):

    molecule = Molecule.from_mapped_smiles(smiles)

    torsion_indices = get_torsion_indices(molecule, central_bond)
    assert sorted(torsion_indices) == sorted(expected_values)
