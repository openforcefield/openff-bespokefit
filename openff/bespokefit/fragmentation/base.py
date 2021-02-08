"""
Register new fragmentation methods with bespokefit
"""
from typing import Dict, List, Union

from openff.bespokefit.exceptions import FragmenterError
from openff.bespokefit.fragmentation.fragmenter import WBOFragmenter
from openff.bespokefit.fragmentation.model import FragmentEngine

fragment_engines: Dict[str, FragmentEngine] = {}


def register_fragment_engine(
    fragment_engine: FragmentEngine, replace: bool = False
) -> None:
    """
    Register a new valid fragment engine with bespokefit.

    Parameters:
        fragment_engine: The fragment engine class that should be registered.
        replace: If the fragment engine should replace another registered with the same name.

    Raises:
        FragmenterError
            If the fragment engine is already registered or if the FragmentEngine object is not compatible.
    """

    if isinstance(fragment_engine, FragmentEngine):
        fragment_name = fragment_engine.fragmentation_engine.lower()
        if fragment_name not in fragment_engines or (
            fragment_name in fragment_engines and replace
        ):
            fragment_engines[fragment_name] = fragment_engine
        else:
            raise FragmenterError(
                f"An fragmentation engine is already registered under the name {fragment_engine.fragmentation_engine}, to replace this please use the `replace=True` flag."
            )
    else:
        raise FragmenterError(
            f"The optimizer {fragment_engine} could not be registered it must be a subclass of openff.bespokefit.fragmentation.FragmentEngine"
        )


def deregister_fragment_engine(fragment_engine: Union[FragmentEngine, str]) -> None:
    """
    Remove a frgamnetation engine from the list of valid fragmenters.

    Parameters:
        fragment_engine: The FragmentEngine class or name of the class that should be removed.
    """

    if isinstance(fragment_engine, FragmentEngine):
        fragment_name = fragment_engine.fragmentation_engine.lower()
    else:
        fragment_name = fragment_engine.lower()

    fragmenter = fragment_engines.pop(fragment_name, None)
    if fragmenter is None:
        raise FragmenterError(
            f"The fragmentation engine {fragment_engine} was not registered with bespokefit."
        )


def get_fragmentation_engine(fragmentation_engine: str, **kwargs) -> FragmentEngine:
    """
    Get the fragmentation engine class from the list of registered optimizers in bespokefit by name.

    Parameters:
        fragment_engine: The name of the fragment engine that should be fetched
        kwargs: Any kwargs that should be passed into the fragmentation engine to initialise the object.

    Returns:
        The requested fragmentation engine matching the given fragment engine name.
    """

    fragmenter = fragment_engines.get(fragmentation_engine.lower(), None)
    if fragmenter is None:
        raise FragmenterError(
            f"The fragment engine {fragmentation_engine} was not registered with bespokefit."
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

    return list(fragment_engines.keys())


# register the built in optimizers
register_fragment_engine(WBOFragmenter())