import networkx as nx
from chemper.graphs.environment import ChemicalEnvironment


def compare_smirks_graphs(smirks1: str, smirks2: str) -> bool:
    """
    Compare two smirks schema based on the types of smirks they cover.
    """
    if smirks1 == smirks2:
        return True

    # define the node matching functions
    def atom_match(atom1, atom2):
        """
        A networkx matching function for atom smirks.
        """
        return atom1["index"] == atom2["index"]

    def bond_match(atom1, atom2):
        """
        A networkx matching function for bond smirks.
        """
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
        """
        A networkx matching function for angle smirks.
        """

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
        """
        A networkx matching function for dihedral smirks.
        """
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
        env1_graph, env2_graph, node_match=node_match
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


def validate_smirks(smirks: str, expected_tags: int) -> str:
    """
    Make sure the supplied smirks has the correct number of tagged atoms.
    """

    smirk = ChemicalEnvironment(smirks=smirks)
    tagged_atoms = len(smirk.get_indexed_atoms())

    assert tagged_atoms == expected_tags, (
        f"The smirks pattern ({smirks}) has {tagged_atoms} tagged atoms, but should "
        f"have {expected_tags}."
    )

    return smirks
