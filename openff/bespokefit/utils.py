import contextlib
import os
import shutil
from pathlib import Path
from typing import List, Tuple, Union

import networkx as nx
import numpy as np
from chemper.graphs.environment import ChemicalEnvironment
from openforcefield import topology as off
from openforcefield.typing.engines.smirnoff import (
    AngleHandler,
    BondHandler,
    ImproperTorsionHandler,
    ProperTorsionHandler,
    vdWHandler,
)
from pkg_resources import resource_filename

from openff.qcsubmit.common_structures import MoleculeAttributes
from openff.qcsubmit.datasets import ComponentResult
from openff.qcsubmit.factories import BasicDatasetFactory, TorsiondriveDatasetFactory


def read_qdata(qdata_file: str) -> Tuple[List[np.array], List[float], List[np.array]]:
    """
    Read a torsiondrive and forcebalance qdata files and return the geometry energy and gradients.

    Parameters
    ----------
    qdata_file: str
        The file path to the torsiondrive and forcebalance qdata files.
    """

    coords, energies, gradients = [], [], []
    with open(qdata_file) as qdata:
        for line in qdata.readlines():
            if "COORDS" in line:
                geom = np.array(line.split()[1:])
                energies.append(geom)
            elif "ENERGY" in line:
                energies.append(float(line.split()[-1]))
            elif "GRADIENT" in line:
                grad = np.array(line.split()[1:])
                gradients.append(grad)

    return coords, energies, gradients


def compare_smirks_graphs(smirks1: str, smirks2: str):
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
        print(atom1, atom2)
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
    # first work out the type of graph, atom, angle, dihedral based on the number of tagged atoms
    env1 = ChemicalEnvironment(smirks1)
    env2 = ChemicalEnvironment(smirks2)
    # make sure they tag the same number of atoms
    if len(env1.get_indexed_atoms()) != len(env2.get_indexed_atoms()):
        return False
    else:
        smirks_type = len(env1.get_indexed_atoms())

    # define the general node match
    def general_match(x, y):
        is_equal = x["_or_types"] == y["_or_types"]
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


def get_molecule_cmiles(molecule: off.Molecule) -> MoleculeAttributes:
    """
    Generate the molecule cmiles data.
    """
    factory = BasicDatasetFactory()
    return factory.create_cmiles_metadata(molecule)


def get_torsiondrive_index(molecule: off.Molecule) -> str:
    """
    Generate a QCSubmit torsiondrive dataset index name for the molecule with an atom map.
    """
    factory = TorsiondriveDatasetFactory()
    return factory.create_index(molecule)


def deduplicated_list(
    molecules: Union[off.Molecule, List[off.Molecule], str]
) -> ComponentResult:
    """
    Create a deduplicated list of molecules based on the input type.
    """
    input_file, molecule, input_directory = None, None, None

    if isinstance(molecules, str):
        # this is an input file or folder
        if os.path.isfile(molecules):
            input_file = molecules
        else:
            input_directory = molecules

    elif isinstance(molecules, off.Molecule):
        molecule = [
            molecules,
        ]
    else:
        molecule = molecules

    return ComponentResult(
        component_name="default",
        component_provenance={},
        component_description={},
        molecules=molecule,
        input_file=input_file,
        input_directory=input_directory,
    )


def get_data(relative_path):
    """
    Get the file path to some data in the qcsubmit package.
    Parameters:
        relative_path: The relative path to the data
    """

    fn = resource_filename("openff.bespokefit", os.path.join("data", relative_path))

    if not os.path.exists(fn):
        raise ValueError(
            f"Sorry! {fn} does not exist. If you just added it, you'll have to re-install"
        )

    return fn


@contextlib.contextmanager
def forcebalance_setup(folder_name: str, keep_files: bool = True):
    """
    Create and enter a forcebalance fitting folder and setup the targets and forcefield sub-dirs.
    """
    cwd = os.getcwd()
    print("making forcebalance file system in ", cwd)
    os.mkdir(folder_name)
    print("making master folder", folder_name)
    os.chdir(folder_name)
    os.mkdir("forcefield")
    os.mkdir("targets")
    print("yield to fb run")
    yield
    os.chdir(cwd)
    if not keep_files:
        shutil.rmtree(folder_name, ignore_errors=True)


@contextlib.contextmanager
def task_folder(folder_name: str, keep_files: bool = True):
    """
    Create a master folder for the bespoke task which all optimization stages will be performed in.
    """
    cwd = os.getcwd()
    Path(folder_name).mkdir(parents=True, exist_ok=True)
    os.chdir(folder_name)
    yield
    os.chdir(cwd)
    if not keep_files:
        shutil.rmtree(folder_name, ignore_errors=True)


def smirks_from_off(
    off_smirks: Union[
        AngleHandler.AngleType,
        vdWHandler.vdWType,
        BondHandler.BondType,
        ProperTorsionHandler.ProperTorsionType,
        ImproperTorsionHandler.ImproperTorsionType,
    ]
) -> Union["AtomSmirks", "BondSmirks", "AngleSmirks", "TorsionSmirks"]:
    """ "
    Build and Bespokefit smirks parameter object from the openforcefield toolkit equivalent object.
    """
    from .schema.smirks import AngleSmirks, AtomSmirks, BondSmirks, TorsionSmirks

    # map the off types to the bespoke types
    _off_to_smirks = {
        "Angle": AngleSmirks,
        "Atom": AtomSmirks,
        "Bond": BondSmirks,
        "ProperTorsion": TorsionSmirks,
        "ImproperTorsion": TorsionSmirks,
    }
    # build the smirks and update it
    smirk = _off_to_smirks[off_smirks._VALENCE_TYPE].from_off_smirks(
        off_smirk=off_smirks
    )
    return smirk
