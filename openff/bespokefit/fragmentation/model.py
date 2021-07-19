"""
Here we implement the basic fragmentation class.
"""
import abc
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from openff.qcsubmit.common_structures import MoleculeAttributes
from openff.toolkit.topology import Molecule
from typing_extensions import Literal

from openff.bespokefit.schema.bespoke import FragmentSchema
from openff.bespokefit.utilities.pydantic import ClassBase

if TYPE_CHECKING:
    from openff.fragmenter.fragment import FragmentationResult


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

    @classmethod
    def provenance(cls) -> Dict[str, str]:
        """
        Return the provenance of the the fragmentEngine.
        """
        from openff import fragmenter, toolkit
        from openff.bespokefit.utilities.provenance import (
            get_ambertools_version,
            get_openeye_versions,
        )

        prov = {
            "openff-fragmenter": fragmenter.__version__,
            "openff-toolkit": toolkit.__version__,
        }

        # check if we have openeye
        openeye = get_openeye_versions()
        if openeye:
            prov.update(openeye)
        else:
            # we used rdkit and AT
            from rdkit import rdBase

            prov["rdkit"] = rdBase.rdkitVersion
            prov["ambertools"] = get_ambertools_version()

        return prov
