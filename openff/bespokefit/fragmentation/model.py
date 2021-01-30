"""
Here we implement the basic fragmentation class.
"""
import abc
from typing import Dict, List

from openforcefield.topology import Molecule
from pydantic import BaseModel, Field

from openff.bespokefit.common_structures import FragmentData


class FragmentEngine(BaseModel, abc.ABC):
    """
    The base Fragment engine class which controls the type of fragmentation that should be performed.
    New fragmentation engines can be implemented by subclassing and registering new class.
    """

    fragmentation_engine: str = Field(
        ..., description="The name of the Fragmentation engine."
    )
    description: str = Field(
        ..., description="A description of the fragmentation engine."
    )

    class Config:
        validate_assignment = True
        arbitrary_types_allowed = True

    @classmethod
    @abc.abstractmethod
    def is_available(cls) -> bool:
        """
        This method should identify is the component can be used by checking if the dependencies are available and
        if not returning a message on how to install them.

        Returns:
            `True` if the fragmentation method can be used else `False`
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def fragment(self, molecule: Molecule) -> List[FragmentData]:
        """
        This method should fragment the given input molecule and return the FragmentData schema which details
        how the fragment is related to the parent.
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def provenance(self) -> Dict:
        """
        This function should detail the programs used in running this fragmentation engine and their versions.
        """

        raise NotImplementedError()

    @staticmethod
    def _get_fragment_parent_mapping(
        fragment: Molecule, parent: Molecule
    ) -> Dict[int, int]:
        """
        Get a mapping between two molecules of different size ie a fragment to a parent.

        Parameters
        ----------
        fragment: off.Molecule
            The fragment molecule that we want to map on to the parent.
        parent: off.Molecule
            The parent molecule the fragment was made from.

        Notes
        -----
            As the MCS is used to create the mapping it will not be complete, that is some fragment atoms have no relation to the parent.

        Returns
        -------
        Dict[int, int]
            A mapping between the fragment and the parent molecule.
        """

        # check to see if we can do a normal mapping in the toolkit
        isomorphic, atom_map = Molecule.are_isomorphic(
            fragment,
            parent,
            return_atom_map=True,
            aromatic_matching=False,
            bond_order_matching=False,
            bond_stereochemistry_matching=False,
            atom_stereochemistry_matching=False,
        )
        if atom_map is not None:
            return atom_map

        else:
            # this molecule are different sizes so now we can use rdkit trick
            return FragmentEngine._get_rdkit_mcs_mapping(fragment, parent)

    @staticmethod
    def _get_rdkit_mcs_mapping(fragment: Molecule, parent: Molecule) -> Dict[int, int]:
        """
        Use rdkit MCS function to find the maximum mapping between the fragment and parent molecule.
        """

        from rdkit import Chem
        from rdkit.Chem import rdFMCS

        parent_rdkit = parent.to_rdkit()
        fragment_rdkit = fragment.to_rdkit()
        mcs = rdFMCS.FindMCS(
            [parent_rdkit, fragment_rdkit],
            atomCompare=rdFMCS.AtomCompare.CompareElements,
            bondCompare=rdFMCS.BondCompare.CompareAny,
            ringMatchesRingOnly=True,
            completeRingsOnly=True,
        )
        # make a new molecule from the mcs
        match_mol = Chem.MolFromSmarts(mcs.smartsString)
        # get the mcs parent/fragment mapping
        matches_parent = parent_rdkit.GetSubstructMatch(match_mol)
        matches_fragment = fragment_rdkit.GetSubstructMatch(match_mol)
        mapping = dict(zip(matches_fragment, matches_parent))
        return mapping
