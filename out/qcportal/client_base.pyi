from . import __version__ as __version__
from .exceptions import AuthenticationFailure as AuthenticationFailure
from .serialization import deserialize as deserialize, serialize as serialize
from _typeshed import Incomplete
from typing import Any, Dict, Optional, Type, Union

def pretty_print_request(req) -> None: ...
def pretty_print_response(res) -> None: ...

class PortalRequestError(Exception):
    msg: Incomplete
    status_code: Incomplete
    details: Incomplete
    def __init__(self, msg: str, status_code: int, details: Dict[str, Any]) -> None: ...

class PortalClientBase:
    debug_requests: bool
    address: Incomplete
    username: Incomplete
    timeout: int
    retry_max: int
    retry_delay: float
    retry_backoff: int
    retry_jitter_fraction: float
    server_info: Incomplete
    server_name: Incomplete
    api_limits: Incomplete
    def __init__(self, address: str, username: Optional[str] = None, password: Optional[str] = None, verify: bool = True, show_motd: bool = True) -> None: ...
    @classmethod
    def from_file(cls, server_name: Optional[str] = None, config_path: Optional[str] = None): ...
    @property
    def encoding(self) -> str: ...
    @encoding.setter
    def encoding(self, encoding: str): ...
    def make_request(self, method: str, endpoint: str, response_model: Optional[Type[_V]], *, body_model: Optional[Type[_T]] = None, url_params_model: Optional[Type[_U]] = None, body: Optional[Union[_T, Dict[str, Any]]] = None, url_params: Optional[Union[_U, Dict[str, Any]]] = None, allow_retries: bool = True) -> _V: ...
    def ping(self) -> bool: ...
    def get_server_information(self) -> Dict[str, Any]: ...
