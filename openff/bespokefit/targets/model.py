"""
The base target model.
"""

import abc
from typing import Any, Dict, List, Tuple, Union

import openforcefield.topology as off
from pydantic import BaseModel, Field
from typing_extensions import Literal

from openff.bespokefit.collection_workflows import CollectionMethod, WorkflowStage
from openff.bespokefit.common_structures import ParameterSettings
from openff.qcsubmit.common_structures import QCSpec


class Target(BaseModel, abc.ABC):
    """
    The base target class used to create new targets.
    This acts as a factory which acts on each molecule passed producing fitting targets specific to the molecule.

    """

    name: Literal["Target"] = Field(
        "Target", description="The name of the optimization target."
    )
    description: str = Field(..., description="A description of how the target works.")
    parameter_targets: List[ParameterSettings] = []
    collection_workflow: List[WorkflowStage] = Field(
        [],
        description="The collection workflow details the steps required to generate the input data to fit this target.",
    )
    keywords: Dict[str, Any] = {}
    weight: int
    generate_bespoke_terms: bool = (
        True  # if the target should generate bespoke parameters for the entry or not
    )
    qc_spec: QCSpec = QCSpec(
        method="ani2x",
        basis=None,
        program="torchani",
        spec_name="ani2x",
        spec_description="Ani2x ML spec for torsiondrives.",
    )
    _extra_dependencies = []
    _enum_fields = []

    class Config:
        validate_assignment = True
        allow_mutation = True
        arbitrary_types_allowed = True
        json_encoders = {CollectionMethod: lambda v: v.value}

    def dict(
        self,
        *,
        include: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
        exclude: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
        by_alias: bool = False,
        skip_defaults: bool = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> "DictStrAny":

        # correct the enum dict rep
        data = super().dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )
        for field in self._enum_fields:
            data[field] = getattr(self, field).value
        return data

    @abc.abstractmethod
    def generate_fitting_schema(
        self, molecule: off.Molecule, initial_ff_values: str, **kwargs
    ) -> "TargetSchema":
        """
        Generate the target schema for this molecule. This involves determining which parameters in the molecule should be fit
        , generating any new smirks patterns for the molecule and adding collection jobs to the queue which are required to fit the target.
        """

        raise NotImplementedError()

    def provenance(self) -> Dict[str, Any]:
        """
        Return the basic provenance of the target and any dependencies it may have.

        Note:
            New targets only need to add the name of the dependence to the _extra_dependencies list to have it included.
        """
        import importlib

        import openforcefield
        import openforcefields
        import rdkit

        provenance = {
            "openforcefield": openforcefield.__version__,
            "openforcefields": openforcefields.__version__,
            "rdkit": rdkit.__version__,
            "target": self.name,
        }
        # now loop over the extra dependencies
        for dependency in self._extra_dependencies:
            dep = importlib.import_module(dependency)
            provenance[dependency] = dep.__version__

        return provenance

    @abc.abstractmethod
    def prep_for_fitting(self, fitting_target: "TargetSchema") -> None:
        """
        Some optimizers will need the general schema data to be adapted to suite the optimizer, this should be
        implemented here, and will be called before optimization on each target.
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def local_reference_collection(
        self, fitting_target: "TargetSchema"
    ) -> "TargetSchema":
        """
        If the collection method is type local then this method must be implemented and will be used to collect the data localy prvided the fitting schema.

        Note:
            Bespokefit will handle directory changes.
        """

        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def is_available(cls) -> bool:
        """
        Work out if the module is available depending on the dependencies.
        """

        raise NotImplementedError()

    @staticmethod
    def _get_new_single_graph_smirks(
        atoms: Tuple[int, ...], molecule: off.Molecule, layers: Union[str, int] = "all"
    ) -> str:
        """
        Generate a new smirks pattern for the selected atoms of the given molecule.

        Parameters
        ----------
        atoms: Tuple[int]
            The indices of the atoms that require a new smirks pattern.
        molecule: off.Molecule
            The molecule that that patten should be made for.
        layers: Union[str, int]
            The number of layers that should be included in the pattern, default to all to make it molecule specific.

        Returns
        -------
        str
            A single smirks string encapsulating the atoms requested in the given molecule.
        """

        from chemper.graphs.single_graph import SingleGraph

        graph = SingleGraph(mol=molecule.to_rdkit(), smirks_atoms=atoms, layers=layers)
        return graph.as_smirks(compress=False)

    @staticmethod
    def _get_new_cluster_graph_smirks(
        atoms: List[List[Tuple[int, ...]]],
        molecules: List[off.Molecule],
        layers: int = 1,
    ) -> str:
        """
        Generate a new smirks pattern which matches the requested atoms in all of the molecules.

        Parameters
        ----------
        atoms: List[List[Tuple[int]]]
            A list of the atom indices that require a smirks pattern in the order of the molecules.
        molecules: List[off.Molecule]
            A list of the molecules in the same order as the atom indices.
        layers: int
            The number of layers to be considered when making the pattern.

        Returns
        -------
        str
            A single smirks string which matches all of the atoms requested in each of the molecules.
        """

        from chemper.graphs.cluster_graph import ClusterGraph

        graph = ClusterGraph(
            mols=[mol.to_rdkit() for mol in molecules],
            smirks_atoms_lists=atoms,
            layers=layers,
        )
        return graph.as_smirks(compress=False)

    @staticmethod
    def _get_fragment_parent_mapping(
        fragment: off.Molecule, parent: off.Molecule
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
        isomorphic, atom_map = off.Molecule.are_isomorphic(
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
            return Target._get_rdkit_mcs_mapping(fragment, parent)

    @staticmethod
    def _get_rdkit_mcs_mapping(
        fragment: off.Molecule, parent: off.Molecule
    ) -> Dict[int, int]:
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
