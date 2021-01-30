"""
Implement the openforcefield fragmenter package as a possible fragmentation engine.
"""

from typing import Dict, List

from openforcefield.topology import Molecule
from pydantic import Field

from openff.bespokefit.common_structures import FragmentData
from openff.bespokefit.exceptions import FragmenterError
from openff.bespokefit.fragmentation.model import FragmentEngine


class WBOFragmenter(FragmentEngine):
    """
    Fragment molecules using the WBO Fragmenter class of the openforcefield fragmenter module.
    For more information see <https://github.com/openforcefield/fragmenter>.
    """

    fragmentation_engine = "WBOFragmenter"
    description = (
        "Fragment a molecule across all rotatable bonds using the WBO fragmenter."
    )
    wbo_threshold: float = Field(
        0.03,
        description="The WBO error threshold between the parent and the fragment value, the fragmentation will stop when the difference between the fragment and parent is less than this value.",
    )
    keep_non_rotor_ring_substituents: bool = Field(
        True,
        description="If any non rotor ring substituents should be kept during the fragmentation resulting in smaller fragments.",
    )

    @classmethod
    def is_available(cls) -> bool:
        """
        Check if fragmenter can be imported
        """
        from qcelemental.util import which_import

        openeye = which_import(
            ".oechem",
            raise_error=True,
            return_bool=True,
            package="openeye",
            raise_msg="Please install via `conda install openeye-toolkits -c openeye`.",
        )
        fragmenter = which_import(
            "fragmenter",
            raise_error=True,
            return_bool=True,
            raise_msg="Please install via `conda install fragmenter -c omnia`.",
        )

        return openeye and fragmenter

    def fragment(self, molecule: Molecule) -> List[FragmentData]:
        """
        Fragment the molecule using the WBOFragmenter.

        Parameters:
            molecule: The openff molecule to be fragmented using the provided class settings

        Returns:
            A list of FragmentData schema which details how a parent molecule is related to a fragment and which bond
            we fragmented around.

        Raises:
            FragmenterError: If the molecule can not be fragmented.
        """
        from fragmenter import fragment

        # make sure the molecule has at least one conformer as this can cause issues
        if molecule.n_conformers == 0:
            molecule.generate_conformers(n_conformers=1)

        # set up the fragmenter
        fragment_factory = fragment.WBOFragmenter(
            molecule=molecule.to_openeye(), verbose=False
        )

        fragments: List[FragmentData] = []
        try:
            # fragment the molecule
            fragment_factory.fragment(
                threshold=self.wbo_threshold,
                keep_non_rotor_ring_substituents=self.keep_non_rotor_ring_substituents,
            )
            # now we work out the relation between the fragment and the parent
            fragments_data = fragment_factory.to_torsiondrive_json()
            # now store the data
            for data in fragments_data.values():
                off_frag = Molecule.from_mapped_smiles(
                    data["identifiers"][
                        "canonical_isomeric_explicit_hydrogen_mapped_smiles"
                    ]
                )
                # get the fragment parent mapping
                frag_dihedral = data["dihedral"][0][1:3]

                # in some cases we get one fragment back which is the parent molecule
                # we should not work out a mapping
                print("working out mapping")
                if not molecule.is_isomorphic_with(off_frag):
                    print("mapping not isomorphic work out with rdkit")
                    mapping = self._get_fragment_parent_mapping(
                        fragment=off_frag, parent=molecule
                    )
                    print("got the mapping for fragment ", off_frag)
                    # get the parent torsion
                    parent_dihedral = tuple([mapping[i] for i in frag_dihedral])
                    parent_molecule = molecule
                else:
                    # reuse the current fragment data as dummy parent data
                    mapping = dict((i, i) for i in range(molecule.n_atoms))
                    parent_dihedral = frag_dihedral
                    parent_molecule = off_frag
                # this is the data we need so make the fragmnetdata
                frag_data = FragmentData(
                    parent_molecule=parent_molecule,
                    parent_torsion=parent_dihedral,
                    fragment_molecule=off_frag,
                    fragment_torsion=frag_dihedral,
                    fragment_attributes=data["identifiers"],
                    fragment_parent_mapping=mapping,
                )
                fragments.append(frag_data)

            return fragments

        except RuntimeError:
            raise FragmenterError(
                f"The molecule {molecule} could not be fragmented so no fitting target was made."
            )

    def provenance(self) -> Dict:
        """
        Return the provanace of the the fragmentEngine.
        """
        import fragmenter
        import openeye

        return {"fragmenter": fragmenter.__version__, "openeye": openeye.__version__}
