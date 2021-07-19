"""
Tools to help with bespoke target smirks generation
"""

from typing import Dict, List, Optional, Tuple, Union

from chemper.graphs.cluster_graph import ClusterGraph
from chemper.graphs.single_graph import SingleGraph
from openff.qcsubmit.common_structures import MoleculeAttributes
from openff.toolkit.topology import Molecule
from pydantic import BaseModel, Field
from typing_extensions import Literal

from openff.bespokefit.exceptions import SMIRKSTypeError
from openff.bespokefit.fragmentation.model import FragmentData
from openff.bespokefit.schema.bespoke.smirks import (
    BespokeAngleSmirks,
    BespokeAtomSmirks,
    BespokeBondSmirks,
    BespokeSmirksParameter,
    BespokeTorsionSmirks,
)
from openff.bespokefit.schema.smirnoff import SmirksType
from openff.bespokefit.utilities.smirnoff import ForceFieldEditor


class SmirksGenerator(BaseModel):
    """
    Generates a set of smirks that describe the requested force groups of the molecule,
    these can be bespoke or simply extract the current values from the target forcefield.
    """

    class Config:
        validate_assigment = True
        arbitrary_types_allowed = True

    initial_force_field: Union[str, ForceFieldEditor] = Field(
        "openff_unconstrained-1.3.0.offxml",
        description="The base forcefield the smirks should be generated from.",
    )
    generate_bespoke_terms: bool = Field(
        True,
        description="For each instance of a force group in the molecule generate a new "
        "bespoke smirks parameter.",
    )
    expand_torsion_terms: bool = Field(
        True,
        description="For each new torsion term expand the number of k terms up to 4.",
    )
    target_smirks: List[SmirksType] = Field(
        [SmirksType.ProperTorsions],
        description="The list of parameters the new smirks patterns should be made for.",
    )
    smirks_layers: Union[Literal["all"], int] = Field(
        "all",
        description="The number of layers that should be included into the generated "
        "patterns.",
    )

    def generate_smirks_from_molecules(
        self, molecule: Molecule, central_bond: Optional[Tuple[int, int]] = None
    ) -> [BespokeSmirksParameter]:
        """
        A work around for molecules which need smirks but did not go through the fragmentation engine.

        Here we fake a fragment data object and pass it to the normal workflow.
        """
        fragment_data = FragmentData(
            parent_molecule=molecule,
            parent_torsion=central_bond,
            fragment_molecule=molecule,
            fragment_torsion=central_bond,
            fragment_attributes=MoleculeAttributes.from_openff_molecule(molecule),
            fragment_parent_mapping=dict((i, i) for i in range(molecule.n_atoms)),
        )
        return self.generate_smirks_from_fragments(fragment_data=fragment_data)

    def generate_smirks_from_fragments(
        self, fragment_data: FragmentData
    ) -> List[BespokeSmirksParameter]:
        """The main method of the class which takes an input a FragmentData record and produces
        new smirks patterns for the fragment corresponding to the types set in the target smirks
        list.

        Parameters:
            fragment_data: The fragment data object which captures the parent fragment relation and any targeted torsions.

        Returns:
            A list of new bespoke smirks parameters for the molecule.
        """

        if not self.target_smirks:
            raise SMIRKSTypeError(
                "No smirks targets were provided so no new patterns were made, set a "
                "target and run again."
            )

        # now we need to set the forcefield
        if isinstance(self.initial_force_field, ForceFieldEditor):
            ff = self.initial_force_field
        else:
            ff = ForceFieldEditor(force_field_name=self.initial_force_field)

        # for each requested smirks type generate the parameters
        if self.generate_bespoke_terms:
            new_smirks = self._get_all_bespoke_smirks(
                fragment_data=fragment_data,
                force_field_editor=ff,
            )
        else:
            # we just want to find the existing smirks
            new_smirks = self._get_all_smirks(
                molecule=fragment_data.fragment_molecule,
                force_field_editor=ff,
                central_bond=fragment_data.fragment_torsion,
            )
        # now sort the smirks into a dict
        # all_smirks = dict()
        # for smirk in new_smirks:
        #     all_smirks.setdefault(smirk.type.value, []).append(smirk)

        # now we need to check if we need to expand any torsion smirks
        if self.expand_torsion_terms:
            for smirk in new_smirks:
                if smirk.type == SmirksType.ProperTorsions:
                    for i in range(1, 5):
                        if str(i) not in smirk.terms:
                            smirk.add_torsion_term(f"k{i}")

        return new_smirks

    def _get_all_smirks(
        self,
        molecule: Molecule,
        force_field_editor: ForceFieldEditor,
        central_bond: Optional[Tuple[int, int]] = None,
    ) -> List[BespokeSmirksParameter]:
        """
        The main worker method for extracting current smirks patterns for the molecule,
        this will only extract parameters for the requested groups.
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
                molecule=molecule, central_bond=central_bond
            )
            requested_smirks.extend(torsions)

        # now request all of these smirks from the forcefield
        new_smirks = force_field_editor.get_smirks_parameters(
            molecule=molecule, atoms=requested_smirks
        )
        return new_smirks

    def _get_all_bespoke_smirks(
        self,
        fragment_data: FragmentData,
        force_field_editor: ForceFieldEditor,
    ) -> List[BespokeSmirksParameter]:
        """
        The main worker method for generating new bespoke smirks, this will check which
        parameters are wanted and call each method.

        The new smirks will then have any dummy values set by the initial force field
        values.
        """
        bespoke_smirks = []
        fragment_is_parent = True
        fragment_molecule = fragment_data.fragment_molecule
        # check if the fragment is the same as the parent, do it once for speed
        if fragment_data.parent_molecule != fragment_molecule:
            fragment_is_parent = False

        if SmirksType.Vdw in self.target_smirks:
            atom_smirks = self._get_bespoke_atom_smirks(
                fragment_data=fragment_data, fragment_is_parent=fragment_is_parent
            )
            bespoke_smirks.extend(atom_smirks)
        if SmirksType.Bonds in self.target_smirks:
            bond_smirks = self._get_bespoke_bond_smirks(
                fragment_data=fragment_data, fragment_is_parent=fragment_is_parent
            )
            bespoke_smirks.extend(bond_smirks)
        if SmirksType.Angles in self.target_smirks:
            angle_smirks = self._get_bespoke_angle_smirks(
                fragment_data=fragment_data, fragment_is_parent=fragment_is_parent
            )
            bespoke_smirks.extend(angle_smirks)
        if SmirksType.ProperTorsions in self.target_smirks:
            torsion_smirks = self._get_bespoke_torsion_smirks(
                fragment_data=fragment_data, fragment_is_parent=fragment_is_parent
            )
            bespoke_smirks.extend(torsion_smirks)

        # now we need to update all smirks
        updated_smirks = force_field_editor.get_initial_parameters(
            molecule=fragment_molecule, smirks=bespoke_smirks, clear_existing=True
        )
        return updated_smirks

    def _get_bespoke_atom_smirks(
        self, fragment_data: FragmentData, fragment_is_parent: bool
    ) -> List[BespokeAtomSmirks]:
        """
        For the molecule generate a unique set of bespoke atom smirks.
        """
        atom_smirks = []
        fragment_mol = fragment_data.fragment_molecule
        atoms = [(i,) for i in range(fragment_mol.n_atoms)]
        atom_groups = SmirksGenerator.group_valence_by_symmetry(
            molecule=fragment_mol, valence_terms=atoms
        )
        atom_groups = [*atom_groups.values()]
        # get the fragment atoms
        for atom_group in atom_groups:
            target_atoms = [atom_group]
            target_molecules = [fragment_mol]
            if not fragment_is_parent:
                parent_atoms = [
                    tuple(fragment_data.fragment_parent_mapping[a] for a in atom)
                    for atom in atom_group
                ]
                target_atoms.append(parent_atoms)
                target_molecules.append(fragment_data.parent_molecule)

            smirks = self._get_new_cluster_graph_smirks(
                atoms=target_atoms, molecules=target_molecules
            )

            # make new smirks pattern with dummy params
            new_smirks = BespokeAtomSmirks(
                smirks=smirks,
                epsilon=0,
                rmin_half=0,
                atoms=atom_group,
            )
            if new_smirks not in atom_smirks:
                atom_smirks.append(new_smirks)
            else:
                # update the covered atoms
                index = atom_smirks.index(new_smirks)
                for a in atom_group:
                    atom_smirks[index].atoms.add(a)

        return atom_smirks

    def _get_bespoke_bond_smirks(
        self, fragment_data: FragmentData, fragment_is_parent: bool
    ) -> List[BespokeBondSmirks]:
        """
        For the molecule generate a unique set of bespoke bond smirks.
        """
        bond_smirks = []
        fragment_mol = fragment_data.fragment_molecule
        # group the bonds
        bonds = [(bond.atom1_index, bond.atom2_index) for bond in fragment_mol.bonds]
        bond_groups = SmirksGenerator.group_valence_by_symmetry(fragment_mol, bonds)
        bond_groups = [*bond_groups.values()]
        for bond_group in bond_groups:
            # make a list of the target molecules and bonds, only add the parent if it is different
            target_atoms = [bond_group]
            target_molecules = [fragment_mol]
            if not fragment_is_parent:
                # map the bonds to the parent and use both in the cluster graph
                parent_bonds = [
                    tuple(fragment_data.fragment_parent_mapping[i] for i in bond)
                    for bond in bond_group
                ]
                target_atoms.append(parent_bonds)
                target_molecules.append(fragment_data.parent_molecule)

            smirks = self._get_new_cluster_graph_smirks(
                atoms=target_atoms, molecules=target_molecules
            )
            new_smirks = BespokeBondSmirks(
                smirks=smirks, k=0, length=0, atoms=bond_group
            )
            if new_smirks not in bond_smirks:
                bond_smirks.append(new_smirks)
            else:
                # update the covered atoms
                index = bond_smirks.index(new_smirks)
                bond_smirks[index].atoms.add(bond_group)

        return bond_smirks

    def _get_bespoke_angle_smirks(
        self, fragment_data: FragmentData, fragment_is_parent: bool
    ) -> List[BespokeAngleSmirks]:
        """
        For the molecule generate a unique set of bespoke angle smirks.
        """
        angle_smirks = []
        fragment_mol = fragment_data.fragment_molecule
        angles = [
            tuple([atom.molecule_atom_index for atom in angle])
            for angle in fragment_mol.angles
        ]
        angle_groups = SmirksGenerator.group_valence_by_symmetry(fragment_mol, angles)
        angle_groups = [*angle_groups.values()]

        for angle_group in angle_groups:
            target_atoms = [angle_group]
            target_molecules = [fragment_data.parent_molecule]
            if not fragment_is_parent:
                parent_angles = [
                    tuple(fragment_data.fragment_parent_mapping[i] for i in angle)
                    for angle in angle_group
                ]
                target_atoms.append(parent_angles)
                target_molecules.append(fragment_data.parent_molecule)

            smirks = self._get_new_cluster_graph_smirks(
                atoms=target_atoms, molecules=target_molecules
            )

            new_smirks = BespokeAngleSmirks(
                smirks=smirks,
                k=0,
                angle=0,
                atoms=angle_group,
            )
            if new_smirks not in angle_smirks:
                angle_smirks.append(new_smirks)
            else:
                # update the covered atoms
                index = angle_smirks.index(new_smirks)
                angle_smirks[index].atoms.add(angle_group)

        return angle_smirks

    def _get_bespoke_torsion_smirks(
        self, fragment_data: FragmentData, fragment_is_parent: bool
    ) -> List[BespokeTorsionSmirks]:
        """
        For the molecule generate a unique set of bespoke proper torsion smirks for the
        target bonds or all torsions.
        """

        fragment_mol = fragment_data.fragment_molecule
        # gather a list of torsions
        torsions = self._get_torsion_indices(
            molecule=fragment_mol, central_bond=fragment_data.fragment_torsion
        )

        torsion_smirks = []
        # group the torsions
        torsion_groups = SmirksGenerator.group_valence_by_symmetry(
            fragment_mol, torsions
        )
        torsion_groups = [*torsion_groups.values()]
        for torsion_group in torsion_groups:
            target_atoms = [torsion_group]
            target_molecules = [fragment_mol]
            if not fragment_is_parent:
                parent_torsions = [
                    tuple(fragment_data.fragment_parent_mapping[i] for i in torsion)
                    for torsion in torsion_group
                ]
                target_atoms.append(parent_torsions)
                target_molecules.append(fragment_data.parent_molecule)

            smirks = self._get_new_cluster_graph_smirks(
                atoms=target_atoms, molecules=target_molecules
            )
            new_smirks = BespokeTorsionSmirks(
                smirks=smirks,
                atoms=torsion_group,
            )
            if new_smirks not in torsion_smirks:
                torsion_smirks.append(new_smirks)
            else:
                # update the covered atoms
                index = torsion_smirks.index(new_smirks)
                torsion_smirks[index].atoms.add(torsion_group)

        return torsion_smirks

    def _get_torsion_indices(
        self, molecule: Molecule, central_bond: Optional[Tuple[int, int]] = None
    ) -> List[Tuple[int, int, int, int]]:
        """
        For a given molecule work out the indices of the torsions which need smirks.
        """
        # gather a list of torsions
        torsions = []

        if central_bond is not None:
            target_torsions = self.get_all_torsions(
                bond=central_bond, molecule=molecule
            )
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

    def _get_new_cluster_graph_smirks(
        self, atoms: List[List[Tuple[int, ...]]], molecules: List[Molecule]
    ) -> str:
        """
        Generate a new cluster graph smirks which is valid for the selected atoms in each of the provided molecules.
        """
        graph = ClusterGraph(
            mols=[molecule.to_rdkit() for molecule in molecules],
            smirks_atoms_lists=atoms,
            layers=self.smirks_layers,
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

    @staticmethod
    def group_valence_by_symmetry(
        molecule: Molecule, valence_terms: List[Tuple[int, ...]]
    ) -> Dict[Tuple[int, ...], List[Tuple[int, ...]]]:
        """
        Group the valence term by symmetry useful for deduplication before smirks generation.

        The valence terms are tuples of atoms (0, ) bonds (0, 1) angles (0, 1, 2) or dihedrals (0, 1, 2, 3)

        Parameters:
            molecule: The molecule the valence terms correspond to
            valence_terms: The list of atom tuples that make up the valence term the should be grouped.

        Returns:
            A dictionary of valence terms grouped by symmetry.
        """
        from collections import defaultdict

        # get the symmetry class from either toolkit
        try:
            from rdkit import Chem

            rd_mol = molecule.to_rdkit()
            symmetry_classes = list(Chem.CanonicalRankAtoms(rd_mol, breakTies=False))

        except (ImportError, ModuleNotFoundError):
            from openeye import oechem

            oe_mol = molecule.to_openeye()
            oechem.OEPerceiveSymmetry(oe_mol)

            symmetry_classes_by_index = {
                a.GetIdx(): a.GetSymmetryClass() for a in oe_mol.GetAtoms()
            }
            symmetry_classes = [
                symmetry_classes_by_index[i] for i in range(molecule.n_atoms)
            ]

        # collect by symmetry class
        valence_by_symmetry = defaultdict(list)
        for term in valence_terms:
            valence_symmetry_class = tuple(symmetry_classes[idx] for idx in term)
            if valence_symmetry_class in valence_by_symmetry:
                valence_by_symmetry[valence_symmetry_class].append(term)
            elif tuple(reversed(valence_symmetry_class)) in valence_by_symmetry:
                valence_by_symmetry[tuple(reversed(valence_symmetry_class))].append(
                    term
                )
            else:
                valence_by_symmetry[valence_symmetry_class].append(term)

        return valence_by_symmetry
