"""
Tools to help with bespoke target smirks generation
"""

from typing import Dict, List, Optional, Tuple, Union

from chemper.graphs.single_graph import SingleGraph
from openforcefield.topology import Molecule
from pydantic import BaseModel, Field

from openff.bespokefit.common_structures import SmirksType
from openff.bespokefit.exceptions import SMIRKSTypeError
from openff.bespokefit.forcefield_tools import ForceFieldEditor
from openff.bespokefit.schema import AngleSmirks, AtomSmirks, BondSmirks, TorsionSmirks


class SmirksGenerator(BaseModel):
    """
    Generates a set of smirks that describe the requested force groups of the molecule, these can be bespoke or simply extract the curent values from the target forcefield.
    """

    class Config:
        validate_assigment = True

    initial_forcefield: str = Field(
        "openff_unconstrained-1.3.0.offxml",
        description="The base forcefield the smirks should be generated from.",
    )
    generate_bespoke_terms: bool = Field(
        True,
        description="For each instance of a force group in the molecule generate a new bespoke smirks parameter.",
    )
    expand_torsion_terms: bool = Field(
        True,
        description="For each new torsion term expand the number of k terms up to 4.",
    )
    target_smirks: List[SmirksType] = Field(
        [SmirksType.ProperTorsions],
        description="The list of parameters the new smirks patterns should be made for.",
    )
    smirks_layers: Union[str, int] = Field(
        1,
        description="The number of layers that should be included into the generated patterns.",
    )

    def generate_smirks(
        self, molecule: Molecule, central_bonds: Optional[List[Tuple[int, int]]] = None
    ) -> Dict:
        """
        The main method of the class which takes an input molecule and can generate new smirks patterns for it corresponding to the types set in the target smirks list.

        Parameters:
            molecule: The openforcefield molecule for which we should make the smirks patterns
            central_bonds: An optional list of central bonds which are used with the TargetTorsions option to specify which torsions need new terms.

        Returns:
            A list of new bespoke smirks parameters for the molecule.
        """

        if not self.target_smirks:
            raise SMIRKSTypeError(
                "No smirks targets were provided so no new patterns were made, set a target and run again."
            )

        # now we need to set the forcefield
        ff = ForceFieldEditor(forcefield_name=self.initial_forcefield)

        # for each requested smirks type generate the parameters
        if self.generate_bespoke_terms:
            new_smirks = self._get_all_bespoke_smirks(
                molecule=molecule, forcefield_editor=ff, central_bonds=central_bonds
            )
        else:
            new_smirks = self._get_all_smirks(
                molecule=molecule, forcefield_editor=ff, central_bonds=central_bonds
            )
        # now sort the smirks into a dict
        all_smirks = dict()
        for smirk in new_smirks:
            all_smirks.setdefault(smirk.type.value, []).append(smirk)

        # now we need to check if we need to expand any torsion smirks
        if self.expand_torsion_terms:
            for smirk in all_smirks.get(SmirksType.ProperTorsions, []):
                for i in range(1, 5):
                    if str(i) not in smirk.terms:
                        smirk.add_torsion_term(f"k{i}")

        return all_smirks

    def _get_all_smirks(
        self,
        molecule: Molecule,
        forcefield_editor: ForceFieldEditor,
        central_bonds: Optional[List[Tuple[int, int]]] = None,
    ) -> List:
        """
        The main worker method for extracting current smirks patterns for the molecule, this will only extract parameters for the requested groups.
        """
        # generate a list of all of the required parameter types
        requested_smirks = []
        if SmirksType.Vdw in self.target_smirks:
            atom_indices = [(i,) for i in range(molecule.n_atoms)]
            requested_smirks.extend(atom_indices)
        if SmirksType.Bonds in self.target_smirks:
            bond_indices = [
                (bond.atom1_index, bond.atom2_index) for bond in molecule.bonds
            ]
            requested_smirks.extend(bond_indices)
        if SmirksType.Angles in self.target_smirks:
            angle_indices = [
                tuple([atom.molecule_atom_index for atom in angle])
                for angle in molecule.angles
            ]
            requested_smirks.extend(angle_indices)
        if SmirksType.ProperTorsions in self.target_smirks:
            torsions = self._get_torsion_indices(
                molecule=molecule, central_bonds=central_bonds
            )
            requested_smirks.extend(torsions)

        # now request all of these smirks from the forcefield
        new_smirks = forcefield_editor.get_smirks_parameters(
            molecule=molecule, atoms=requested_smirks
        )
        return new_smirks

    def _get_all_bespoke_smirks(
        self,
        molecule: Molecule,
        forcefield_editor: ForceFieldEditor,
        central_bonds: Optional[List[Tuple[int, int]]] = None,
    ) -> List:
        """
        The main worker method for generating new bespoke smirks, this will check which parameters are wanted and call each method.
        The new smirks will then have any dummy values set by the initial forcefield values.
        """
        bespoke_smirks = []
        if SmirksType.Vdw in self.target_smirks:
            atom_smirks = self._get_bespoke_atom_smirks(molecule=molecule)
            bespoke_smirks.extend(atom_smirks)
        if SmirksType.Bonds in self.target_smirks:
            bond_smirks = self._get_bespoke_bond_smirks(molecule=molecule)
            bespoke_smirks.extend(bond_smirks)
        if SmirksType.Angles in self.target_smirks:
            angle_smirks = self._get_bespoke_angle_smirks(molecule=molecule)
            bespoke_smirks.extend(angle_smirks)
        if SmirksType.ProperTorsions in self.target_smirks:
            torsion_smirks = self._get_bespoke_torsion_smirks(
                molecule=molecule, central_bonds=central_bonds
            )
            bespoke_smirks.extend(torsion_smirks)

        # now we need to update all smirks
        updated_smirks = forcefield_editor.get_initial_parameters(
            molecule=molecule, smirks=bespoke_smirks, clear_existing=True
        )
        return updated_smirks

    def _get_bespoke_atom_smirks(self, molecule: Molecule) -> List[AtomSmirks]:
        """
        For the molecule generate a unique set of bespoke atom smirks.
        """
        atom_smirks = []

        for i in range(molecule.n_atoms):
            # make new smirks pattern with dummy params
            new_smirks = AtomSmirks(
                smirks=self._get_new_single_graph_smirks(atoms=(i,), molecule=molecule),
                epsilon=0,
                rmin_half=0,
                atoms=[
                    (i,),
                ],
            )
            if new_smirks not in atom_smirks:
                atom_smirks.append(new_smirks)
            else:
                # update the covered atoms
                index = atom_smirks.index(new_smirks)
                atom_smirks[index].atoms.add((i,))

        return atom_smirks

    def _get_bespoke_bond_smirks(self, molecule: Molecule) -> List[BondSmirks]:
        """
        For the molecule generate a unique set of bespoke bond smirks.
        """
        bond_smirks = []
        for bond in molecule.bonds:
            atoms = (bond.atom1_index, bond.atom2_index)
            new_smirks = BondSmirks(
                smirks=self._get_new_single_graph_smirks(
                    atoms=atoms, molecule=molecule
                ),
                k=0,
                length=0,
                atoms=[
                    atoms,
                ],
            )
            if new_smirks not in bond_smirks:
                bond_smirks.append(new_smirks)
            else:
                # update the covered atoms
                index = bond_smirks.index(new_smirks)
                bond_smirks[index].atoms.add(atoms)

        return bond_smirks

    def _get_bespoke_angle_smirks(self, molecule: Molecule) -> List[AngleSmirks]:
        """
        For the molecule generate a unique set of bespoke angle smirks.
        """
        angle_smirks = []
        for angle in molecule.angles:
            atom_ids = tuple([atom.molecule_atom_index for atom in angle])
            new_smirks = AngleSmirks(
                smirks=self._get_new_single_graph_smirks(
                    atoms=atom_ids, molecule=molecule
                ),
                k=0,
                angle=0,
                atoms=[
                    atom_ids,
                ],
            )
            if new_smirks not in angle_smirks:
                angle_smirks.append(new_smirks)
            else:
                # update the covered atoms
                index = angle_smirks.index(new_smirks)
                angle_smirks[index].atoms.add(atom_ids)

        return angle_smirks

    def _get_bespoke_torsion_smirks(
        self, molecule: Molecule, central_bonds: Optional[List[Tuple[int, int]]] = None
    ) -> List[TorsionSmirks]:
        """
        For the molecule generate a unique set of bespoke proper torsion smirks for the target bonds or all torsions.
        """
        # gather a list of torsions
        torsions = self._get_torsion_indices(
            molecule=molecule, central_bonds=central_bonds
        )

        torsion_smirks = []
        for dihedral in torsions:
            new_smirks = TorsionSmirks(
                smirks=self._get_new_single_graph_smirks(
                    atoms=dihedral, molecule=molecule
                ),
                atoms=[
                    dihedral,
                ],
            )
            if new_smirks not in torsion_smirks:
                torsion_smirks.append(new_smirks)
            else:
                # update the covered atoms
                index = torsion_smirks.index(new_smirks)
                torsion_smirks[index].atoms.add(dihedral)

        return torsion_smirks

    def _get_torsion_indices(
        self, molecule: Molecule, central_bonds: Optional[List[Tuple[int, int]]] = None
    ) -> List[Tuple[int, int, int, int]]:
        """
        For a given molecule work out the indices of the torsions which need smirks.
        """
        # gather a list of torsions
        torsions = []

        if central_bonds is not None:
            for bond in central_bonds:
                target_torsions = self.get_all_torsions(bond=bond, molecule=molecule)
                torsions.extend(target_torsions)
        else:
            for proper in molecule.propers:
                target_torsion = tuple([atom.molecule_atom_index for atom in proper])
                torsions.append(target_torsion)
        return torsions

    def _get_new_single_graph_smirks(
        self,
        atoms: Tuple[int, ...],
        molecule: Molecule,
    ) -> str:
        """
        Generate a new smirks pattern for the selected atoms of the given molecule.

        Parameters
        ----------
        atoms: Tuple[int]
            The indices of the atoms that require a new smirks pattern.
        molecule: off.Molecule
            The molecule that that patten should be made for.

        Returns
        -------
        str
            A single smirks string encapsulating the atoms requested in the given molecule.
        """
        graph = SingleGraph(
            mol=molecule.to_rdkit(), smirks_atoms=atoms, layers=self.smirks_layers
        )
        return graph.as_smirks(compress=False)

    @staticmethod
    def get_all_torsions(
        bond: Tuple[int, int], molecule: Molecule
    ) -> List[Tuple[int, int, int, int]]:
        """
        Get all torsions that pass through the central bond to generate smirks patterns.

        Parameters:
            bond: The bond which we want all torsions for.
            molecule: The molecule which the bond corresponds to.

        Returns:
            A list of all of the torsion tuples passing through this central bond.
        """

        torsions = []
        central_bond = molecule.get_bond_between(*bond)
        atom1, atom2 = central_bond.atom1, central_bond.atom2

        for atom in atom1.bonded_atoms:
            for end_atom in atom2.bonded_atoms:
                if atom != atom2 and end_atom != atom1:
                    dihedral = (
                        atom.molecule_atom_index,
                        atom1.molecule_atom_index,
                        atom2.molecule_atom_index,
                        end_atom.molecule_atom_index,
                    )
                    torsions.append(dihedral)
                else:
                    continue

        return torsions
