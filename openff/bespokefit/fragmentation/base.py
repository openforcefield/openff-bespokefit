"""
Register new fragmentation methods with bespokefit
"""
from typing import Dict, List, Union

from openff.bespokefit.exceptions import FragmenterError
from openff.bespokefit.fragmentation.fragmenter import PfizerFragmenter, WBOFragmenter
from openff.bespokefit.fragmentation.model import FragmentEngine

FragmentEngines = Union[WBOFragmenter, PfizerFragmenter]
_fragment_engines: Dict[str, FragmentEngines] = {}


def register_fragment_engine(
    fragment_engine: FragmentEngines, replace: bool = False
) -> None:
    """
    Register a new valid fragment engine with bespokefit.

    Parameters:
        fragment_engine: The fragment engine class that should be registered.
        replace: If the fragment engine should replace another registered with the same
            name.

    Raises:
        FragmenterError
            If the fragment engine is already registered or if the FragmentEngine object
            is not compatible.
    """

    if issubclass(type(fragment_engine), FragmentEngine):
        fragment_name = fragment_engine.type.lower()
        if fragment_name not in _fragment_engines or (
            fragment_name in _fragment_engines and replace
        ):
            _fragment_engines[fragment_name] = fragment_engine
        else:
            raise FragmenterError(
                f"An fragmentation engine is already registered under the name "
                f"{fragment_engine.type}, to replace this please use "
                f"the `replace=True` flag."
            )
    else:
        raise FragmenterError(
            f"The optimizer {fragment_engine} could not be registered it must be a "
            f"subclass of openff.bespokefit.fragmentation.FragmentEngine"
        )


def deregister_fragment_engine(fragment_engine: Union[FragmentEngines, str]) -> None:
    """
    Remove a frgamnetation engine from the list of valid fragmenters.

    Parameters:
        fragment_engine: The FragmentEngine class or name of the class that should be
            removed.
    """

    try:
        fragment_name = fragment_engine.type.lower()
    except AttributeError:
        fragment_name = fragment_engine.lower()

    fragmenter = _fragment_engines.pop(fragment_name, None)
    if fragmenter is None:
        raise FragmenterError(
            f"The fragmentation engine {fragment_engine} was not registered with "
            f"bespokefit."
        )


def get_fragmentation_engine(fragmentation_engine: str, **kwargs) -> FragmentEngines:
    """
    Get the fragmentation engine class from the list of registered optimizers in
    bespokefit by name.

    Parameters:
        fragmentation_engine: The name of the fragment engine that should be fetched
        kwargs: Any kwargs that should be passed into the fragmentation engine to
            initialise the object.

    Returns:
        The requested fragmentation engine matching the given fragment engine name.
    """

    fragmenter = _fragment_engines.get(fragmentation_engine.lower(), None)
    if fragmenter is None:
        raise FragmenterError(
            f"The fragment engine {fragmentation_engine} was not registered with "
            f"bespokefit."
        )

    if kwargs:
        return fragmenter.parse_obj(kwargs)
    else:
        return fragmenter


def list_fragment_engines() -> List[str]:
    """
    Get the list of registered fragmentation engines with bespokefit.

    Returns:
        A list of the fragmentation engine classes registered.
    """

    return list(_fragment_engines.keys())


# register the built in optimizers
register_fragment_engine(WBOFragmenter())
register_fragment_engine(PfizerFragmenter())
