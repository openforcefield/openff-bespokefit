import contextlib
import os
import shutil
from typing import Dict, List, Tuple, Union

import networkx as nx
import numpy as np
from openforcefield import topology as off
from pkg_resources import resource_filename

from chemper.graphs.environment import ChemicalEnvironment
from qcsubmit.datasets import (
    BasicDataset,
    ComponentResult,
    OptimizationDataset,
    TorsiondriveDataset,
)
from qcsubmit.factories import BasicDatasetFactory, TorsiondriveDatasetFactory

from .collection_workflows import CollectionMethod


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
    def node_match(x, y):
        is_equal = x["_or_types"] == y["_or_types"]
        is_equal &= x["_and_types"] == y["_and_types"]
        is_equal &= x["ring"] == y["ring"]
        is_equal &= x["is_atom"] == y["is_atom"]
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
    nodes = list(chem_env._graph.nodes())
    new_graph.add_nodes_from([(node, node.__dict__) for node in nodes])
    new_graph.add_edges_from(list(chem_env._graph.edges()))
    return new_graph


def get_molecule_cmiles(molecule: off.Molecule) -> Dict[str, str]:
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
    os.mkdir(folder_name)
    os.chdir(folder_name)
    os.mkdir("forcefield")
    os.mkdir("targets")
    yield
    os.chdir(cwd)
    if not keep_files:
        shutil.rmtree(folder_name)


def schema_to_datasets(
    schema: List["MoleculeSchema"],
    singlepoint_name: str = "Bespokefit single points",
    optimization_name: str = "Bespokefit optimizations",
    torsiondrive_name: str = "Bespokefit torsiondrives",
) -> List[Union[BasicDataset, OptimizationDataset, TorsiondriveDataset]]:
    """
    Generate a set of qcsubmit datasets containing all of the tasks required to compute the QM data.

    Parameters:
        schema: A list Molecule input schema which the tasks can be extracted from
        singlepoint_name: The common name of the single point datasets used for hessian, energy and gradients
        optimization_name: The name of the optimization dataset
        torsiondrive_name: The name of the torsiondrive dataset

    Note:
        Local custom tasks not possible in QCArchive are not included and will be ran when the fitting queue is started.
        Hessian datasets can not be produced until the initial optimization is complete
        The task hash will also be embedded into the entry to make updating the results faster.
    """

    description = "A bespoke-fit generated dataset to be used for parameter optimization for more information please visit https://github.com/openforcefield/bespoke-fit."
    # set up each dataset
    energy_dataset = BasicDataset(
        qc_specifications={},
        dataset_name=singlepoint_name + " energy",
        driver="energy",
        description=description,
    )
    gradient_dataset = BasicDataset(
        qc_specifications={},
        dataset_name=singlepoint_name + " gradient",
        driver="gradient",
        description=description,
    )
    hessian_dataset = BasicDataset(
        qc_specifications={},
        dataset_name=singlepoint_name + " hessian",
        driver="hessian",
        description=description,
    )
    opt_dataset = OptimizationDataset(
        qc_specifications={},
        dataset_name=optimization_name,
        description=description,
    )
    torsion_dataset = TorsiondriveDataset(
        qc_specifications={},
        dataset_name=torsiondrive_name,
        description=description,
    )

    method_to_dataset = {
        CollectionMethod.Optimization: opt_dataset,
        CollectionMethod.Hessian: hessian_dataset,
        CollectionMethod.Energy: energy_dataset,
        CollectionMethod.Gradient: gradient_dataset,
        CollectionMethod.TorsionDrive1D: torsion_dataset,
        CollectionMethod.TorsionDrive2D: torsion_dataset,
    }
    # now generate a list of current tasks and assign them to a dataset
    hashes = set()

    # get all of the current tasks per molecule
    for molecule in schema:
        tasks = molecule.get_task_map()
        for job_hash, task_entries in tasks.items():
            task = task_entries[0]
            if job_hash not in hashes:
                if (
                    task.collection_stage.method == CollectionMethod.TorsionDrive1D
                    or task.collection_stage.method == CollectionMethod.TorsionDrive2D
                ):
                    # we just need to make the index now
                    molecule = task.entry.current_molecule
                    dihedrals = task.entry.extras["dihedrals"][0]
                    attributes = task.entry.attributes
                    attributes["task_hash"] = job_hash
                    atom_map = dict((atom, i) for i, atom in enumerate(dihedrals))
                    molecule.properties["atom_map"] = atom_map
                    index = get_torsiondrive_index(molecule)
                    torsion_dataset.add_molecule(
                        index=index,
                        molecule=molecule,
                        attributes=attributes,
                        dihedrals=[
                            dihedrals,
                        ],
                    )
                    hashes.add(job_hash)
                    # is this how we want to handle different specs for different jobs
                    # this will run every job at all specs which is not wanted
                    if (
                        task.entry.qc_spec
                        not in torsion_dataset.qc_specifications.values()
                    ):
                        torsion_dataset.add_qc_spec(**task.entry.qc_spec.dict())

                elif task.collection_stage.method in method_to_dataset.keys():
                    # get the entry metadata
                    molecule = task.entry.current_molecule
                    attributes = task.entry.attributes
                    attributes["task_hash"] = job_hash
                    index = molecule.to_smiles(
                        isomeric=True,
                        mapped=False,
                        explicit_hydrogens=False,
                    )
                    # get the specific dataset type
                    dataset = method_to_dataset[task.collection_stage.method]
                    dataset.add_molecule(
                        index=index,
                        molecule=molecule,
                        attributes=attributes,
                    )
                    hashes.add(job_hash)
                    if task.entry.qc_spec not in dataset.qc_specifications.values():
                        dataset.add_qc_spec(**task.entry.qc_spec.dict())

                else:
                    # this is a local task
                    continue

            else:
                # this task has already been submitted
                continue
    # build up the return datasets this stops torsiondrive dataset from adding twice
    datasets = []
    for dataset in method_to_dataset.values():
        if dataset not in datasets and dataset.n_molecules > 0:
            datasets.append(dataset)

    return datasets
