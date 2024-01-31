from ..base_models import QueryIteratorBase as QueryIteratorBase, QueryModelBase as QueryModelBase, RestModelBase as RestModelBase
from qcelemental.models import Molecule
from qcelemental.models.molecule import Identifiers as MoleculeIdentifiers
from typing import Dict, List, Optional

class MoleculeQueryFilters(QueryModelBase):
    molecule_id: Optional[List[int]]
    molecule_hash: Optional[List[str]]
    molecular_formula: Optional[List[str]]
    identifiers: Optional[Dict[str, List[str]]]

class MoleculeModifyBody(RestModelBase):
    name: Optional[str]
    comment: Optional[str]
    identifiers: Optional[MoleculeIdentifiers]
    overwrite_identifiers: bool

class MoleculeQueryIterator(QueryIteratorBase[Molecule]):
    def __init__(self, client, query_filters: MoleculeQueryFilters) -> None: ...
