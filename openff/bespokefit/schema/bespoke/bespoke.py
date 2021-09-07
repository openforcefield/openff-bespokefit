from typing import Any, Dict, List, Optional, Tuple

from openff.qcsubmit.common_structures import MoleculeAttributes
from openff.toolkit.topology import Molecule
from pydantic import Field

from openff.bespokefit.utilities.pydantic import SchemaBase


class FragmentSchema(SchemaBase):
    """A basic data class which records the relation between a parent molecule and a
    fragment of it.
    """

    parent_torsion: Tuple[int, int] = Field(
        ...,
        description="The target torsion in the parent molecule which was fragmented "
        "around.",
    )
    fragment_torsion: Tuple[int, int] = Field(
        ...,
        description="The corresponding indices of the fragment torsion which maps to "
        "the parent torsion.",
    )
    fragment_attributes: MoleculeAttributes = Field(
        ..., description="The full set of cmiles descriptors for this molecule."
    )
    fragment_parent_mapping: Dict[int, int] = Field(
        ...,
        description="The mapping from the fragment to the parent atoms, so "
        "fragment_parent_mapping[i] would give the index of the atom in the parent "
        "which is equivalent to atom i.",
    )

    @property
    def molecule(self) -> Molecule:
        """Build the graph of the fragment molecule"""
        return Molecule.from_mapped_smiles(
            self.fragment_attributes.canonical_isomeric_explicit_hydrogen_mapped_smiles
        )

    @property
    def target_dihedral(self) -> Tuple[int, int, int, int]:
        """
        Return a target dihedral that could be driven for the target central bond.
        """
        from openff.bespokefit.bespoke.smirks import SmirksGenerator

        dihedrals = SmirksGenerator.get_all_torsions(
            bond=self.fragment_torsion, molecule=self.molecule
        )
        molecule = self.molecule

        # now find the dihedral with the heavest termial atoms
        target_dihedral = None
        max_weight = 0
        for dihedral in dihedrals:
            weight = sum([molecule.atoms[i].atomic_number for i in dihedral])
            if weight > max_weight:
                target_dihedral = dihedral
                max_weight = weight

        return target_dihedral


class MoleculeSchema(SchemaBase):
    """This is the main fitting schema which wraps a molecule object with settings and
    information about the target to be fit and the reference data."""

    attributes: MoleculeAttributes = Field(
        ...,
        description="The full set of molecule cmiles descriptors which can be used to "
        "build the molecule.",
    )
    task_id: str = Field(
        ...,
        description="An id given to the parameterization of this molecule to separate "
        "when multiple molecules are to be parameterized separately.",
    )
    fragment_data: Optional[List[FragmentSchema]] = Field(
        None, description="The list of fragment which corespond to this molecule."
    )
    fragmentation_engine: Optional[Dict[str, Any]] = Field(
        None,
        description="The fragmentation engine and settings used to fragment this "
        "molecule.",
    )

    @property
    def molecule(self) -> Molecule:
        """Get the openff molecule representation of the input target molecule."""
        return Molecule.from_mapped_smiles(
            self.attributes.canonical_isomeric_explicit_hydrogen_mapped_smiles
        )

    @property
    def fragments(self) -> List[Molecule]:
        """Get a unique list of the fragments in this molecule."""
        unique_mols = []
        for fragment in self.fragment_data:
            fragment_mol = fragment.molecule
            if fragment_mol not in unique_mols:
                unique_mols.append(fragment_mol)
        return unique_mols

    def add_fragment(self, fragment: FragmentSchema) -> None:
        """Add a new fragment schema to this molecule."""
        if self.fragment_data is None:
            self.fragment_data = []
        self.fragment_data.append(fragment)
