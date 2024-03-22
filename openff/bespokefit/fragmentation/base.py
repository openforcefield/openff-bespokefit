"""Register new fragmentation methods with bespokefit."""

from typing import Union

from openff.fragmenter.fragment import Fragmenter, PfizerFragmenter, WBOFragmenter

from openff.bespokefit.exceptions import FragmenterError

_fragmentation_engines: dict[str, type[Fragmenter]] = {}


def register_fragmentation_engine(
    engine: type[Fragmenter],
    replace: bool = False,
) -> None:
    """
    Register a new valid fragment engine with bespokefit.

    Parameters
    ----------
    engine: Fragmenter
        The fragment engine class that should be registered.
    replace: bool
        If the fragment engine should replace another registered with the same name.

    Raises
    ------
    FragmenterError
        If the fragment engine is already registered or if the FragmentEngine object is not compatible.

    """
    if not issubclass(engine, Fragmenter):
        raise FragmenterError(
            f"The {engine} fragmentation engine could not be registered "
            f"it must be a subclass of `openff.fragmenter.fragment.Fragmenter`.",
        )

    scheme = engine.__name__.lower()

    if scheme in _fragmentation_engines and not replace:
        raise FragmenterError(
            f"An fragmentation engine is already registered under the name "
            f"{engine.__name__}, to replace this please use "
            f"the `replace=True` flag.",
        )

    _fragmentation_engines[scheme] = engine


def deregister_fragmentation_engine(engine: Union[type[Fragmenter], str]) -> None:
    """
    Remove a fragmentation engine from the list of valid options.

    Parameters
    ----------
    engine : str or class
        The class or name of the engine that should be removed.

    """
    scheme = engine.lower() if isinstance(engine, str) else engine.__name__.lower()

    existing_type = _fragmentation_engines.pop(scheme, None)

    if existing_type is None:
        raise FragmenterError(
            f"The fragmentation engine {engine} was not registered with "
            f"bespokefit.",
        )


def get_fragmentation_engine(engine: str) -> "FragmentationEngine":
    """
    Get the fragmentation engine class from the list of registered engines by name.

    Parameters
    ----------
    engine : str
        The name of the fragment engine that should be fetched

    Returns
    -------
        The requested fragmentation engine matching the given fragment engine name.

    """
    fragmenter = _fragmentation_engines.get(engine.lower(), None)

    if fragmenter is None:
        raise FragmenterError(
            f"The fragment engine {engine} was not registered with " f"bespokefit.",
        )

    return fragmenter


def list_fragmentation_engines() -> list[str]:
    """
    Get the list of registered fragmentation engines with bespokefit.

    Returns
    -------
        A list of the fragmentation engine classes registered.

    """
    return list(_fragmentation_engines.keys())


register_fragmentation_engine(WBOFragmenter)
register_fragmentation_engine(PfizerFragmenter)

FragmentationEngine = Union[tuple(_fragmentation_engines.values())]
