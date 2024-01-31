from _typeshed import Incomplete
from chemper.chemper_utils import is_valid_smirks as is_valid_smirks
from chemper.graphs.cluster_graph import ClusterGraph as ClusterGraph
from chemper.graphs.single_graph import SingleGraph as SingleGraph
from chemper.mol_toolkits import mol_toolkit as mol_toolkit

def make_frag_graph(smiles, layers): ...
def make_cluster_graph(smiles_list, layers: int = 0): ...

graph_data: Incomplete
graphs: Incomplete

def test_other_cluster_graph(graph1, graph2) -> None: ...
def test_smirks_frag_graph(graph, expected, expected_compressed) -> None: ...
