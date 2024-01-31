from _typeshed import Incomplete
from chemper.graphs.cluster_graph import ClusterGraph as ClusterGraph
from chemper.graphs.single_graph import SingleGraph as SingleGraph
from chemper.mol_toolkits import mol_toolkit as mol_toolkit

def test_empty_graph(graph_method) -> None: ...

smiles_set: Incomplete
layers_options: Incomplete
frag_combos: Incomplete

def test_no_fail_fragment(smile, layers) -> None: ...

cluster_combos: Incomplete

def test_no_fail_cluster(smiles_list, layers) -> None: ...
def test_mols_mismatch() -> None: ...
