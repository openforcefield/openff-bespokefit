import importlib
import sys

import pytest
from openff.toolkit import Molecule

from openff.bespokefit.utilities.molecule import (
    _oe_canonical_atom_order,
    _oe_get_atom_symmetries,
    _rd_canonical_atom_order,
    _rd_get_atom_symmetries,
    canonical_order_atoms,
    get_atom_symmetries,
    get_torsion_indices,
    group_valence_by_symmetry,
)


@pytest.fixture()
def with_oe_backend(monkeypatch):
    oechem = pytest.importorskip("openeye.oechem")

    if not oechem.OEChemIsLicensed():
        pytest.skip("OE is not licensed")

    monkeypatch.setitem(sys.modules, "rdkit", None)


@pytest.fixture()
def with_rd_backend(monkeypatch):
    pytest.importorskip("rdkit")
    monkeypatch.setitem(sys.modules, "openeye", None)
    monkeypatch.setitem(sys.modules, "openeye.oechem", None)


def test_oe_fixture(with_oe_backend):
    """Ensure that our fixture really does ensure only OE can be used"""

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("rdkit")


@pytest.mark.parametrize(
    "module, package",
    [("openeye", None), ("openeye.oechem", None), ("openeye", "oechem")],
)
def test_rd_fixture(with_rd_backend, module, package):
    """Ensure that our fixture really does ensure only RDKit can be used"""

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module, package)


@pytest.mark.parametrize(
    "get_symmetries, backend",
    [
        (_oe_get_atom_symmetries, "with_oe_backend"),
        (_rd_get_atom_symmetries, "with_rd_backend"),
        (get_atom_symmetries, "with_oe_backend"),
        (get_atom_symmetries, "with_rd_backend"),
    ],
)
def test_get_atom_symmetries(get_symmetries, backend, request):
    molecule = Molecule.from_mapped_smiles("[H:1][C:2]([H:3])([H:4])[O:5][H:6]")

    request.getfixturevalue(backend)

    try:
        atom_symmetries = get_symmetries(molecule)

    except ModuleNotFoundError as e:
        pytest.skip(f"missing optional dependency - {e.name}")
        return

    assert len({atom_symmetries[i] for i in (0, 2, 3)}) == 1
    assert len({atom_symmetries[i] for i in (1, 4, 5)}) == 3


@pytest.mark.parametrize(
    "canonical_order_func",
    [_oe_canonical_atom_order, _rd_canonical_atom_order],
)
def test_canonical_atom_order(canonical_order_func):
    molecule = Molecule.from_mapped_smiles("[H:1][C:2]([H:3])([H:4])[O:5][H:6]")

    try:
        atom_order = canonical_order_func(molecule)

    except ModuleNotFoundError as e:
        pytest.skip(f"missing optional dependency - {e.name}")
        return

    # In general the canonical order should have H ranked first and heavy atoms last.
    assert sorted(atom_order[i] for i in [0, 2, 3, 5]) == [0, 1, 2, 3]
    assert sorted(atom_order[i] for i in [1, 4]) == [4, 5]


@pytest.mark.parametrize("backend", ["with_rd_backend", "with_oe_backend"])
def test_canonical_order_atoms(backend, request):
    molecule = Molecule.from_mapped_smiles("[H:1][C:2]([H:3])([H:4])[O:5][H:6]")
    molecule.properties["atom_map"] = {i: i + 1 for i in range(molecule.n_atoms)}

    request.getfixturevalue(backend)

    canonical_molecule = canonical_order_atoms(molecule)
    assert [a.atomic_number for a in canonical_molecule.atoms] in (
        [6, 8, 1, 1, 1, 1],
        [8, 6, 1, 1, 1, 1],
    )

    canonical_atom_map = canonical_molecule.properties["atom_map"]

    # Make sure the atom map has been updated to reflect that the heavy atoms are now at
    # the beginning of the molecule
    assert (canonical_atom_map[0], canonical_atom_map[1]) in [(2, 5), (5, 2)]


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
