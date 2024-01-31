from .addons import using_networkx as using_networkx
from _typeshed import Incomplete
from qcelemental.testing import compare as compare, compare_values as compare_values

do_plot: bool
verbose: int
run_mirror: bool
uno_cutoff: float
simpleR: Incomplete
simpleS: Incomplete

def test_simpleS() -> None: ...

clbrbutRR: Incomplete
clbrbutRS: Incomplete
clbrbutSR: Incomplete
clbrbutSS: Incomplete

def test_clbrbutSS() -> None: ...
def test_clbrbutSR_vs_RR() -> None: ...
def test_clbrbutRS() -> None: ...
def test_clbrbutSR_vs_RS() -> None: ...

dibromobutSS: Incomplete
dibromobutSR: Incomplete
dibromobutRS: Incomplete
dibromobutRR: Incomplete

def test_dibromobutRS_RR() -> None: ...
def test_dibromobutSS_RR() -> None: ...
def test_dibromobutRS_SS() -> None: ...
def test_dibromobutRS_SR_nomirror() -> None: ...
def test_dibromobutRS_SR() -> None: ...

chiralanem: Incomplete
chiralaneopt: Incomplete

def toobig2() -> None: ...

water16a: Incomplete
water16b: Incomplete

def toobig() -> None: ...
