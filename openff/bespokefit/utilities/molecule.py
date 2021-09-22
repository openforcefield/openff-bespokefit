from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from openff.toolkit.topology import Molecule


def _oe_get_atom_symmetries(molecule: Molecule) -> List[int]:

    from openeye import oechem

    oe_mol = molecule.to_openeye()
    oechem.OEPerceiveSymmetry(oe_mol)

    symmetry_classes_by_index = {
        a.GetIdx(): a.GetSymmetryClass() for a in oe_mol.GetAtoms()
    }
    return [symmetry_classes_by_index[i] for i in range(molecule.n_atoms)]


def _rd_get_atom_symmetries(molecule: Molecule) -> List[int]:

    from rdkit import Chem

    rd_mol = molecule.to_rdkit()
    return list(Chem.CanonicalRankAtoms(rd_mol, breakTies=False))


def get_atom_symmetries(molecule: Molecule) -> List[int]:

    try:
        return _oe_get_atom_symmetries(molecule)
    except (ImportError, ModuleNotFoundError):
        return _rd_get_atom_symmetries(molecule)


def get_torsion_indices(
    molecule: Molecule, central_bond: Optional[Tuple[int, int]] = None
) -> List[Tuple[int, int, int, int]]:
    """Returns the indices of all torsions in a molecule, optionally returning only
    those that involve a specified central bond.

    Args:
        molecule: The molecule of interest
        central_bond: The (optional) indices of the bond each torsion should
            be centered around.

    Returns:
        The indices of each torsion.
    """

    # gather a list of torsions
    torsions = []

    if central_bond is not None:

        central_bond = molecule.get_bond_between(*central_bond)
        atom_b, atom_c = central_bond.atom1, central_bond.atom2

        target_torsions = [
            (
                atom_a.molecule_atom_index,
                atom_b.molecule_atom_index,
                atom_c.molecule_atom_index,
                atom_d.molecule_atom_index,
            )
            for atom_a in atom_b.bonded_atoms
            if atom_a != atom_c
            for atom_d in atom_c.bonded_atoms
            if atom_d != atom_b
        ]
        torsions.extend(target_torsions)

    else:

        for proper in molecule.propers:
            target_torsion = tuple([atom.molecule_atom_index for atom in proper])
            torsions.append(target_torsion)

    return torsions


def group_valence_by_symmetry(
    molecule: Molecule, valence_terms: List[Tuple[int, ...]]
) -> Dict[Tuple[int, ...], List[Tuple[int, ...]]]:
    """Group the a set of valence terms by symmetry groups.

    The valence terms are tuples of atoms (0, ) bonds (0, 1) angles (0, 1, 2) or
    dihedrals (0, 1, 2, 3)

    Parameters:
        molecule: The molecule the valence terms correspond to
        valence_terms: The list of atom tuples that make up the valence term the
            should be grouped.

    Returns:
        A dictionary of valence terms grouped by symmetry.
    """

    symmetry_classes = get_atom_symmetries(molecule)

    # collect by symmetry class
    valence_by_symmetry = defaultdict(list)

    for term in valence_terms:

        valence_symmetry_class = tuple(symmetry_classes[idx] for idx in term)
        valence_symmetry_class_reversed = tuple(reversed(valence_symmetry_class))

        if valence_symmetry_class_reversed in valence_by_symmetry:
            valence_symmetry_class = valence_symmetry_class_reversed

        valence_by_symmetry[valence_symmetry_class].append(term)

    return valence_by_symmetry
