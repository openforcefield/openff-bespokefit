"""Utilities for dealing with SMIRKS."""

import copy
from typing import Literal, Optional, Union

import networkx as nx
from chemper.graphs.cluster_graph import ClusterGraph
from chemper.graphs.environment import ChemicalEnvironment
from openff.fragmenter.utils import get_atom_index
from openff.toolkit.topology import Molecule
from openff.toolkit.typing.engines.smirnoff import ParameterType, ProperTorsionHandler
from openff.units import unit
from pydantic import Field

from openff.bespokefit.exceptions import SMIRKSTypeError
from openff.bespokefit.schema.smirnoff import SMIRNOFFParameter, get_smirnoff_parameter
from openff.bespokefit.utilities.molecule import (
    get_torsion_indices,
    group_valence_by_symmetry,
)
from openff.bespokefit.utilities.pydantic import SchemaBase
from openff.bespokefit.utilities.smirnoff import ForceFieldEditor, SMIRKSType


def get_cached_torsion_parameters(
    molecule: Molecule,
    bespoke_parameter: ProperTorsionHandler.ProperTorsionType,
    cached_parameters: list[ProperTorsionHandler.ProperTorsionType],
) -> Optional[ProperTorsionHandler.ProperTorsionType]:
    """
    For a given molecule update the input parameter with cached values if an equivalent parameter can be found in the cached list.

    Parameters
    ----------
    molecule: Molecule
        The target molecule the parameter should be applied to
    bespoke_parameter: ProperTorsionType
        Our bespoke parameter which contains the reference smirks pattern
    cached_parameters: List[ProperTorsionType]
        The list of cached parameters which can be reused

    """
    # get matches for our target smirks
    target_matches = molecule.chemical_environment_matches(
        query=bespoke_parameter.smirks,
    )
    target_matches = {m for match in target_matches for m in match}

    # make sure the cached parameter hits the same atoms as our bespoke parameter
    for cached_parameter in cached_parameters:
        matches = molecule.chemical_environment_matches(query=cached_parameter.smirks)
        matches = {m for match in matches for m in match}
        if not target_matches.symmetric_difference(matches):
            cached_parameter.add_cosmetic_attribute(
                attr_name="cached",
                attr_value="True",
            )
            # we keep the new bespoke smirks to ensure it matches the parent and the fragment
            cached_parameter.smirks = bespoke_parameter.smirks
            return cached_parameter

    return None


def compare_smirks_graphs(smirks1: str, smirks2: str) -> bool:
    """Compare two smirks schema based on the types of smirks they cover."""
    if smirks1 == smirks2:
        return True

    # define the node matching functions
    def atom_match(atom1, atom2):
        """Networkx matching function for atom smirks."""
        return atom1["index"] == atom2["index"]

    def bond_match(atom1, atom2):
        """Networkx matching function for bond smirks."""
        if atom1["index"] == atom2["index"]:
            return True
        elif atom1["index"] > 0 and atom2["index"] > 0:
            if abs(atom1["index"] - atom2["index"]) == 1:
                return True
            else:
                return False
        else:
            return False

    def angle_match(atom1, atom2):
        """Networkx matching function for angle smirks."""
        if atom1["index"] == atom2["index"]:
            return True
        elif atom1["index"] > 0 and atom2["index"] > 0:
            if abs(atom1["index"] - atom2["index"]) == 2:
                return True
            else:
                return False
        else:
            return False

    def dihedral_match(atom1, atom2):
        """Networkx matching function for dihedral smirks."""
        if atom1["index"] == atom2["index"]:
            return True
        elif atom1["index"] > 0 and atom2["index"] > 0:
            if abs(atom1["index"] - atom2["index"]) == 3:
                return True
            elif abs(atom1["index"] - atom2["index"]) == 1:
                return True
            else:
                return False
        else:
            return False

    environments = {1: atom_match, 2: bond_match, 3: angle_match, 4: dihedral_match}

    # first work out the type of graph, atom, angle, dihedral based on the number of
    # tagged atoms
    env1 = ChemicalEnvironment(smirks1)
    env2 = ChemicalEnvironment(smirks2)
    # make sure they tag the same number of atoms
    if len(env1.get_indexed_atoms()) != len(env2.get_indexed_atoms()):
        return False
    else:
        smirks_type = len(env1.get_indexed_atoms())

    # define the general node match
    def general_match(x, y):
        is_equal = (
            any([or_type in x["_or_types"] for or_type in y["_or_types"]])
            if x["_or_types"] != y["_or_types"]
            else True
        )
        is_equal &= x["_and_types"] == y["_and_types"]
        is_equal &= x["ring"] == y["ring"]
        is_equal &= x["is_atom"] == y["is_atom"]
        return is_equal

    def node_match(x, y):
        is_equal = general_match(x, y)
        is_equal &= environments[smirks_type](x, y)
        return is_equal

    # now do the check
    env1_graph = make_smirks_attribute_graph(env1)
    env2_graph = make_smirks_attribute_graph(env2)
    gm = nx.algorithms.isomorphism.GraphMatcher(
        env1_graph,
        env2_graph,
        node_match=node_match,
    )
    return gm.is_isomorphic()


def make_smirks_attribute_graph(chem_env: ChemicalEnvironment) -> nx.Graph:
    """
    Make a new nx.Graph from the environment with attributes.
    """
    new_graph = nx.Graph()
    bonds = chem_env._graph_edges(data=True)
    nodes = list(chem_env._graph.nodes())
    new_graph.add_nodes_from([(node, node.__dict__) for node in nodes])
    # new_graph.add_edges_from(
    #     [(bond[0], bond[1], bond[-1]["bond"].__dict__) for bond in bonds]
    # )
    new_graph.add_edges_from(bonds)
    return new_graph


class SMIRKSettings(SchemaBase):
    """
    Settings for the generation of SMIRKS patterns via the SMIRKSGenerator.
    """

    expand_torsion_terms: bool = Field(
        True,
        description="If the number of k values for each torsion should be expanded beyond what is in "
        "the initial force field to introduce extra degrees of freedom during fitting.",
    )
    generate_bespoke_terms: bool = Field(
        True,
        description="If we should generate bespoke smirks for the molecule or use existing general patterns.",
    )


class SMIRKSGenerator(SMIRKSettings):
    """
    Generates a set of smirks that describe the requested force groups of the molecule.

    These can be bespoke or simply extract the current values from the target forcefield.

    """

    class Config(SMIRKSettings.Config):
        """Pydantic Config."""

        arbitrary_types_allowed = True

    initial_force_field: Union[str, ForceFieldEditor] = Field(
        "openff_unconstrained-1.3.0.offxml",
        description="The base forcefield the smirks should be generated from.",
    )

    target_smirks: list[SMIRKSType] = Field(
        [SMIRKSType.ProperTorsions],
        description="The list of parameters the new smirks patterns should be made for.",
    )

    smirks_layers: Union[Literal["all"], int] = Field(
        "all",
        description="The number of layers that should be included into the generated "
        "patterns.",
    )

    def generate_smirks_from_molecule(
        self,
        molecule: Molecule,
        central_bond: Optional[tuple[int, int]] = None,
    ):
        """Generate SMIRKS patterns that encompass an entire molecule."""
        molecule = copy.deepcopy(molecule)
        molecule.properties["atom_map"] = {i: i + 1 for i in range(molecule.n_atoms)}

        return self.generate_smirks_from_fragment(
            molecule,
            molecule,
            (
                None
                if central_bond is None
                else (central_bond[0] + 1, central_bond[1] + 1)
            ),
        )

    def generate_smirks_from_fragment(
        self,
        parent: Molecule,
        fragment: Molecule,
        fragment_map_indices: Optional[tuple[int, int]],
    ) -> list[ParameterType]:
        """
        Generate a set of smirks patterns for the fragment corresponding to the types set in the target smirks list.

        Parameters
        ----------
        parent: Molecule
            The parent molecule that was fragmented.
        fragment: Molecule
            The fragment of the parent molecule. The map indices in the fragment must match the map indices of the parent.
        fragment_map_indices: tuple[int, int]
            The **map** indices of the atoms that the fragment was generated around.

        Returns
        -------
            A dictionary of new bespoke smirks parameters for the molecule as well as
            an initial guess of their values.

        """
        if not self.target_smirks:
            raise SMIRKSTypeError(
                "No smirks targets were provided so no new patterns were made, set a "
                "target and run again.",
            )

        if isinstance(self.initial_force_field, ForceFieldEditor):
            ff = self.initial_force_field
        else:
            ff = ForceFieldEditor(force_field=self.initial_force_field)

        if self.generate_bespoke_terms:
            new_parameters = self._get_bespoke_parameters(
                force_field_editor=ff,
                parent=parent,
                fragment=fragment,
                fragment_map_indices=fragment_map_indices,
            )

        else:
            new_parameters = self._get_existing_parameters(
                force_field_editor=ff,
                molecule=parent,
                molecule_map_indices=fragment_map_indices,
            )

        # now we need to check if we need to expand any torsion smirks
        if self.expand_torsion_terms:
            for parameter in new_parameters:
                if not isinstance(parameter, ProperTorsionHandler.ProperTorsionType):
                    continue

                # parameters have been split so set all to 1.0 as idivf may have changed
                parameter.idivf = [1.0] * 4
                default_k = [0 * unit.kilocalories_per_mole] * 4
                default_phase = [
                    0 * unit.degree,
                    180 * unit.degree,
                    0 * unit.degree,
                    180 * unit.degree,
                ]
                default_p = [1, 2, 3, 4]

                # update the existing k values for the correct phase and p
                for i, p in enumerate(parameter.periodicity):
                    default_k[p - 1] = parameter.k[i]

                # update with new parameters
                parameter.k = default_k
                parameter.phase = default_phase
                parameter.periodicity = default_p

                # TODO make sure we do not fit interpolated parameters
                if parameter.k_bondorder is not None:
                    raise NotImplementedError(
                        "Bespokefit can not fit interpolated parameters!",
                    )

        return new_parameters

    def _get_existing_parameters(
        self,
        force_field_editor: ForceFieldEditor,
        molecule: Molecule,
        molecule_map_indices: Optional[tuple[int, int]] = None,
    ) -> list[ParameterType]:
        """
        Extract current smirks patterns for the molecule.

        This will only extract parameters for the requested groups.

        """
        requested_smirks = {}
        for smirks_type in self.target_smirks:
            for valence_term in self._get_valence_terms(
                molecule=molecule,
                smirks_type=smirks_type,
                torsion_bond=(
                    None
                    if molecule_map_indices is None
                    else (
                        get_atom_index(molecule, molecule_map_indices[0]),
                        get_atom_index(molecule, molecule_map_indices[1]),
                    )
                ),
            ):
                requested_smirks.setdefault(smirks_type, []).append(valence_term)

        # now request all of these smirks from the forcefield
        new_parameters = force_field_editor.get_parameters(
            molecule=molecule,
            atoms_by_type=requested_smirks,
        )
        return new_parameters

    def _get_bespoke_parameters(
        self,
        force_field_editor: ForceFieldEditor,
        parent: Molecule,
        fragment: Molecule,
        fragment_map_indices: Optional[tuple[int, int]],
    ) -> list[ParameterType]:
        """
        Generate new bespoke smirks.

        This will check which parameters are wanted and call each method.
        The new smirks will then have any dummy values set by the initial force field values.

        """
        fragment_is_parent = parent.to_smiles(
            mapped=False,
            isomeric=False,
        ) == fragment.to_smiles(mapped=False, isomeric=False)

        bespoke_smirks = []
        for smirk_type in self.target_smirks:
            bespoke_smirks.extend(
                self._get_bespoke_smirks(
                    parent=parent,
                    fragment=fragment,
                    fragment_map_indices=fragment_map_indices,
                    fragment_is_parent=fragment_is_parent,
                    smirks_type=smirk_type,
                ),
            )

        # now we need to update all smirks
        new_parameters = force_field_editor.get_initial_parameters(
            molecule=fragment,
            smirks=bespoke_smirks,
        )
        return new_parameters

    def _get_bespoke_smirks(
        self,
        parent: Molecule,
        fragment: Molecule,
        fragment_map_indices: Optional[tuple[int, int]],
        fragment_is_parent: bool,
        smirks_type: SMIRKSType,
    ) -> list[SMIRNOFFParameter]:
        """For the molecule generate a unique set of bespoke smirks of a given type."""
        bespoke_smirks = []

        valence_terms = self._get_valence_terms(
            fragment,
            smirks_type,
            (
                None
                if fragment_map_indices is None
                else (
                    get_atom_index(fragment, fragment_map_indices[0]),
                    get_atom_index(fragment, fragment_map_indices[1]),
                )
            ),
        )
        valence_groups = [*group_valence_by_symmetry(fragment, valence_terms).values()]

        for valence_group in valence_groups:
            target_atoms = [valence_group]
            target_molecules = [fragment]

            if not fragment_is_parent:
                parent_atoms = self._get_parent_valence_terms(
                    parent,
                    fragment,
                    valence_group,
                )

                target_atoms.append(parent_atoms)
                target_molecules.append(parent)

            graph = ClusterGraph(
                mols=[molecule.to_rdkit() for molecule in target_molecules],
                smirks_atoms_lists=target_atoms,
                layers=self.smirks_layers,
            )
            parameter = get_smirnoff_parameter(smirks_type)(
                smirks=graph.as_smirks(compress=False),
                attributes=set(),
            )
            bespoke_smirks.append(parameter)

        return bespoke_smirks

    @staticmethod
    def _get_valence_terms(
        molecule: Molecule,
        smirks_type: SMIRKSType,
        torsion_bond: Optional[tuple[int, int]] = None,
    ) -> list[tuple[int, ...]]:
        if smirks_type == SMIRKSType.Vdw:
            return [(i,) for i in range(molecule.n_atoms)]

        elif smirks_type == SMIRKSType.Bonds:
            return [(bond.atom1_index, bond.atom2_index) for bond in molecule.bonds]

        elif smirks_type == SMIRKSType.Angles:
            return [
                tuple([atom.molecule_atom_index for atom in angle])
                for angle in molecule.angles
            ]

        elif smirks_type == SMIRKSType.ProperTorsions:
            return get_torsion_indices(molecule=molecule, central_bond=torsion_bond)

        raise NotImplementedError()

    @staticmethod
    def _get_parent_valence_terms(
        parent: Molecule,
        fragment: Molecule,
        fragment_valence_terms: list[tuple[int, ...]],
    ) -> list[tuple[int, ...]]:
        """
        Generate a list of parent valence terms that match a set of fragment valence terms.

        Notes
        -----
            * Any terms which are missing in the parent are dropped.

        """
        fragment_atom_to_map_index = fragment.properties["atom_map"]

        parent_map_to_atom_index = {
            j: i for i, j in parent.properties["atom_map"].items()
        }

        parent_terms = []

        for fragment_term in fragment_valence_terms:
            try:
                parent_valence = tuple(
                    parent_map_to_atom_index[fragment_atom_to_map_index[i]]
                    for i in fragment_term
                )
                parent_terms.append(parent_valence)

            except KeyError:
                pass

        return parent_terms
