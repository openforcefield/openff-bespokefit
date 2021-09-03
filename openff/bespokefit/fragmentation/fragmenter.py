"""
Implement the OpenFF fragmenter package as a possible fragmentation engine.
"""

from typing import List

from openff.toolkit.topology import Molecule
from pydantic import Field
from typing_extensions import Literal

from openff.bespokefit.fragmentation.model import FragmentData, FragmentEngine


class WBOFragmenter(FragmentEngine):
    """
    Fragment molecules using the WBO Fragmenter class of the OpenFF fragmenter
    module.

    For more information see <https://github.com/openforcefield/openff-fragmenter>.
    """

    type: Literal["WBOFragmenter"] = "WBOFragmenter"

    wbo_threshold: float = Field(
        0.03,
        description="The WBO error threshold between the parent and the fragment "
        "value, the fragmentation will stop when the difference between the fragment "
        "and parent is less than this value.",
    )
    keep_non_rotor_ring_substituents: bool = Field(
        True,
        description="If any non rotor ring substituents should be kept during the "
        "fragmentation resulting in smaller fragments.",
    )

    @classmethod
    def description(cls) -> str:
        return "Fragment a molecule across all rotatable bonds using the WBO openff-fragmenter."

    def fragment(self, molecule: Molecule) -> List[FragmentData]:
        """
        Fragment the molecule using the WBOFragmenter.

        Parameters:
            molecule: The openff molecule to be fragmented using the provided class
                settings

        Returns:
            A list of FragmentData schema which details how a parent molecule is related
            to a fragment and which bond we fragmented around.

        Raises:
            FragmenterError: If the molecule can not be fragmented.
        """
        from openff.fragmenter.fragment import WBOFragmenter

        # set up the fragmenter
        fragment_factory = WBOFragmenter(
            threshold=self.wbo_threshold,
            keep_non_rotor_ring_substituents=self.keep_non_rotor_ring_substituents,
        )

        try:
            # fragment the molecule
            result = fragment_factory.fragment(
                molecule=molecule, target_bond_smarts=self.target_bond_smarts
            )
            fragments = self.build_fragment_data(result=result)

        except RuntimeError:
            fragments = self.build_fragments_from_parent(molecule=molecule)

        return fragments


class PfizerFragmenter(FragmentEngine):
    """
    Fragment molecules using the fragmentation scheme from (doi: 10.1021/acs.jcim.9b00373), implemented in
    openff-fragmenter <https://github.com/openforcefield/openff-fragmenter>.
    """

    type: Literal["PfizerFragmenter"] = "PfizerFragmenter"

    @classmethod
    def description(cls) -> str:
        return "Fragment a molecule across all rotatable bonds using the Pfizer scheme implemented by openff-fragmenter."

    def fragment(self, molecule: Molecule) -> List[FragmentData]:
        """
        Fragment the input molecule acrros all rotatable bonds using the Pfizer fragmentation scheme.
        """
        from openff.fragmenter.fragment import PfizerFragmenter

        # set up the fragmenter
        fragment_factory = PfizerFragmenter()

        try:
            # fragment the molecule
            result = fragment_factory.fragment(
                molecule=molecule, target_bond_smarts=self.target_bond_smarts
            )
            fragments = self.build_fragment_data(result=result)

        except RuntimeError:
            fragments = self.build_fragments_from_parent(molecule=molecule)

        return fragments
