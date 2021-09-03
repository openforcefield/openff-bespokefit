"""
Here we implement the basic fragmentation class.
"""
import abc
import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from openff.qcsubmit.common_structures import MoleculeAttributes
from openff.toolkit.topology import Molecule
from openff.utilities.provenance import get_ambertools_version
from pydantic import Field
from typing_extensions import Literal

from openff.bespokefit.schema.bespoke import FragmentSchema
from openff.bespokefit.utilities.pydantic import ClassBase

if TYPE_CHECKING:
    from openff.fragmenter.fragment import FragmentationResult

logger = logging.getLogger(__name__)


class FragmentData(ClassBase):
    """A simple dataclass that holds the relation between a parent molecule and the
    fragment.
    """

    parent_molecule: Molecule
    parent_torsion: Optional[Tuple[int, int]] = None
    fragment_molecule: Molecule
    fragment_torsion: Optional[Tuple[int, int]] = None
    fragment_attributes: MoleculeAttributes
    fragment_parent_mapping: Dict[int, int]

    def fragment_schema(self) -> FragmentSchema:
        """
        Convert to a fragment schema.
        """

        schema = FragmentSchema(
            parent_torsion=self.parent_torsion,
            fragment_torsion=self.fragment_torsion,
            fragment_attributes=self.fragment_attributes,
            fragment_parent_mapping=self.fragment_parent_mapping,
        )
        return schema


class FragmentEngine(ClassBase, abc.ABC):
    """The base Fragment engine class which controls the type of fragmentation that
    should be performed. New fragmentation engines can be implemented by subclassing and
    registering new class.
    """

    type: Literal["FragmentEngine"] = "FragmentEngine"
    target_bond_smarts: Optional[List[str]] = Field(
        None,
        description="An optional list of SMARTS patterns that should be used to identify"
        "the rotatable bonds to fragment around. If ``None`` is passed this will default to all"
        "none terminal rotatable bonds.",
    )

    @classmethod
    @abc.abstractmethod
    def description(cls) -> str:
        """A friendly description of the fragmentation engine and links to more info"""

        raise NotImplementedError()

    @classmethod
    def is_available(cls) -> bool:
        """
        Check if fragmenter can be imported
        """
        from qcelemental.util import which_import

        toolkit = which_import(
            ".toolkit",
            raise_error=True,
            return_bool=True,
            package="openff",
            raise_msg="Please install via `conda install openff-toolkit -c conda-forge`.",
        )
        fragmenter = which_import(
            ".fragmenter",
            raise_error=True,
            return_bool=True,
            package="openff",
            raise_msg="Please install via `conda install openff-fragmenter -c conda-forge`.",
        )

        return toolkit and fragmenter

    @abc.abstractmethod
    def fragment(self, molecule: Molecule) -> List[FragmentData]:
        """
        This method should fragment the given input molecule and return the FragmentData
        schema which details how the fragment is related to the parent.
        """

        raise NotImplementedError()

    @classmethod
    def build_fragment_data(cls, result: "FragmentationResult") -> List[FragmentData]:
        """
        A general function to build the fragment data from the result of an openff-fragmenter job.

        Note:
            This function builds the mapping relation from map indices.
        """
        import copy

        from openff.fragmenter.utils import get_atom_index, get_map_index

        fragment_data = []
        parent_mol = result.parent_molecule
        parent_mol_no_map = copy.deepcopy(parent_mol)
        del parent_mol_no_map.properties["atom_map"]
        for bond_map, fragment in result.fragments_by_bond.items():
            fragment_mol = fragment.molecule
            # get the index of the atoms in the fragment for the bond
            atom1, atom2 = get_atom_index(fragment_mol, bond_map[0]), get_atom_index(
                fragment_mol, bond_map[1]
            )
            # the fragment molecule has the same map indices as the parent on atoms that they both contain
            mapping = {}
            for i in range(fragment_mol.n_atoms):
                try:
                    map_idx = get_map_index(fragment_mol, i)
                    parent_atom = get_atom_index(parent_mol, map_idx)
                    mapping[i] = parent_atom
                except KeyError:
                    # the atom has no mapping so it must be missing in the parent
                    continue
            # now remove the atom mapping so the attributes are correct
            del fragment_mol.properties["atom_map"]
            fragment_data.append(
                FragmentData(
                    parent_molecule=parent_mol_no_map,
                    parent_torsion=(
                        get_atom_index(parent_mol, bond_map[0]),
                        get_atom_index(parent_mol, bond_map[1]),
                    ),
                    fragment_molecule=copy.deepcopy(fragment_mol),
                    fragment_torsion=(atom1, atom2),
                    fragment_attributes=MoleculeAttributes.from_openff_molecule(
                        fragment_mol
                    ),
                    fragment_parent_mapping=mapping,
                )
            )
        return fragment_data

    def build_fragments_from_parent(self, molecule: Molecule) -> List[FragmentData]:
        """
        When a molecule can not be fragmented due to stereochemistry issues, this method can build dummy fragment data
        for each eligible rotatable bond.

        Note:
            All possible rotatable bonds are found and deduplicated by molecule symmetry before deciding which ones should be scanned.
        """
        from openff.qcsubmit.workflow_components import ScanEnumerator

        logger.warning(
            f"The molecule {molecule} could not be fragmented and so the full parent will be used instead. This may result in slower fitting times."
        )

        scanner = ScanEnumerator()
        # tag all possible scans
        scanner.add_torsion_scan("[!#1:1]~[!$(*#*)&!D1:2]-,=;!@[!$(*#*)&!D1:3]~[!#1:4]")
        final_mol = scanner.apply(
            molecules=[molecule], processors=1, verbose=False
        ).molecules[0]
        # now for each one build a dummy fragment data
        fragment_data = []
        for torsion in final_mol.properties["dihedrals"].torsions.keys():
            fragment_data.append(
                FragmentData(
                    parent_molecule=final_mol,
                    parent_torsion=torsion,
                    fragment_molecule=final_mol,
                    fragment_torsion=torsion,
                    fragment_attributes=MoleculeAttributes.from_openff_molecule(
                        final_mol
                    ),
                    fragment_parent_mapping=dict(
                        (i, i) for i in range(final_mol.n_atoms)
                    ),
                )
            )

        return fragment_data

    @classmethod
    def provenance(cls) -> Dict[str, str]:
        """
        Return the provenance of the the fragmentEngine.
        """
        from openff import fragmenter, toolkit

        prov = {
            "openff-fragmenter": fragmenter.__version__,
            "openff-toolkit": toolkit.__version__,
        }

        try:

            import openeye

            prov["openeye"] = openeye.__version__

        except ImportError:

            # we used rdkit and AT
            from rdkit import rdBase

            prov["rdkit"] = rdBase.rdkitVersion
            prov["ambertools"] = get_ambertools_version()

        return prov
