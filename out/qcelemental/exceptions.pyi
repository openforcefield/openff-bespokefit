from _typeshed import Incomplete

class NotAnElementError(Exception):
    message: Incomplete
    def __init__(self, atom, strict: bool = False) -> None: ...

class DataUnavailableError(Exception):
    message: Incomplete
    def __init__(self, dataset, atom) -> None: ...

class MoleculeFormatError(Exception):
    message: Incomplete
    def __init__(self, msg) -> None: ...

class ValidationError(Exception):
    message: Incomplete
    def __init__(self, msg) -> None: ...

class ChoicesError(Exception):
    message: Incomplete
    choices: Incomplete
    def __init__(self, msg, choices: Incomplete | None = None) -> None: ...
