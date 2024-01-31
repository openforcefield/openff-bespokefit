from _typeshed import Incomplete
from collections.abc import Generator
from qcelemental.util import which_import as which_import

def internet_connection(): ...

using_web: Incomplete
using_msgpack: Incomplete
using_networkx: Incomplete
using_scipy: Incomplete
using_nglview: Incomplete
serialize_extensions: Incomplete

def xfail_on_pubchem_busy() -> Generator[None, None, None]: ...
def drop_qcsk(instance, tnm: str, schema_name: str = None): ...
