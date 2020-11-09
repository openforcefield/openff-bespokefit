"""
Define the basic torsion target class.
"""
import os
from typing import Any, Dict, List, Tuple, Union

from openforcefield import topology as off
from qcsubmit.results import SingleResult
from qcsubmit.serializers import serialize
from simtk import unit

from ..collection_workflows import CollectionMethod, TorsiondriveWorkflow, WorkflowStage
from ..common_structures import FragmentData, ProperTorsionSettings
from ..exceptions import FragmenterError, MissingReferenceError
from ..forcefield_tools import ForceFieldEditor
from ..schema.fitting import FittingEntry, TargetSchema
from ..schema.smirks import TorsionSmirks
from ..utils import get_molecule_cmiles
from .atom_selection import TorsionSelection
from .model import Target


class TorsionDrive1D(Target):
    """
    The basic torsiondrive 1D target this will act as a base class for the specific torsiondrive classes.
    """

    name = "TorsionDrive1D"
    description = "A basic 1D torsiondrive target factory."
    # this tells us which values in the smirks should be parameterized
    parameter_targets: List[ProperTorsionSettings] = [ProperTorsionSettings()]
    collection_workflow: List[WorkflowStage] = TorsiondriveWorkflow
    fragmentation: bool = True  # should we fragment the molecule
    weight: float = 1.0
    torsion_selection: TorsionSelection = (
        TorsionSelection.All
    )  # which bonds should be fit
    fit_gradient: bool = False
    # torsiondrive settings
    grid_spacings: List[int] = [15]
    energy_upper_limit: float = 0.05
    _extra_dependencies = ["chemper"]
    _collection_methods = [
        CollectionMethod.TorsionDrive2D,
        CollectionMethod.TorsionDrive1D,
    ]
    _enum_fields = ["torsion_selection"]

    def _fragment_molecule(self, off_molecule: off.Molecule) -> List[FragmentData]:
        """
        Take a molecule and fragment it using WBOfragmenter across all rotatable bonds.

        Parameters
        ----------
        off_molecule: off.Molecule
            The openforcefield molecule that should be fragmented.

        Returns
        -------
        List[FragmentData]
            A list of FragmentData classes which hold the relations between the parent molecule and the fragment.
        """

        from fragmenter import fragment
        from qcsubmit.factories import TorsiondriveDatasetFactory

        fragment_factory = fragment.WBOFragmenter(
            molecule=off_molecule.to_openeye(), verbose=False
        )

        fragments: List[FragmentData] = []
        try:
            # fragment the molecule
            fragment_factory.fragment(
                threshold=0.03, keep_non_rotor_ring_substituents=False
            )
            # now we work out the relation between the fragment and the parent
            fragments_data = fragment_factory.to_torsiondrive_json()
            # now store the data
            for data in fragments_data.values():
                off_frag = off.Molecule.from_mapped_smiles(
                    data["identifiers"][
                        "canonical_isomeric_explicit_hydrogen_mapped_smiles"
                    ]
                )

                # get the fragment parent mapping
                frag_dihedral = data["dihedral"][0][1:3]

                # in some cases we get one fragment back which is the parent molecule
                # we should not work out a mapping
                if not off_molecule.is_isomorphic_with(off_frag):
                    mapping = self._get_fragment_parent_mapping(
                        fragment=off_frag, parent=off_molecule
                    )
                    # get the parent torsion
                    parent_dihedral = tuple([mapping[i] for i in frag_dihedral])
                    parent_molecule = off_molecule
                else:
                    # reuse the current fragment data as dummy parent data
                    mapping = dict((i, i) for i in range(off_molecule.n_atoms))
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
            # check we have some fragments in some cases the molecule has not been fragmented
            if not fragments:
                factory = TorsiondriveDatasetFactory()
                # get the rotatable bonds
                bonds = off_molecule.find_rotatable_bonds()
                attributes = factory.create_cmiles_metadata(off_molecule)
                for bond in bonds:
                    dihedral = (bond.atom1_index, bond.atom2_index)
                    frag_data = FragmentData(
                        parent_molecule=off_molecule,
                        parent_torsion=dihedral,
                        fragment_molecule=off_molecule,
                        fragment_torsion=dihedral,
                        fragment_attributes=attributes,
                        fragment_parent_mapping=dict(
                            (i, i) for i in range(off_molecule.n_atoms)
                        ),
                    )
                    fragments.append(frag_data)

            return fragments

        except RuntimeError:
            raise FragmenterError(
                f"The molecule {off_molecule} could not be fragmented so no fitting target was made."
            )

    def _generate_bespoke_fragment_smirks(
        self, fragment_data: FragmentData, fragment_torsion: Tuple[int, int, int, int]
    ) -> TorsionSmirks:
        """
        Generate the bespoke fragment smirks.
        """
        if fragment_data.fragment_molecule != fragment_data.parent_molecule:
            parent_torsion = [
                fragment_data.fragment_parent_mapping[i] for i in fragment_torsion
            ]
            smirks = TorsionSmirks(
                atoms={fragment_torsion},
                smirks=self._get_new_cluster_graph_smirks(
                    atoms=[[parent_torsion], [fragment_torsion]],
                    molecules=[
                        fragment_data.parent_molecule,
                        fragment_data.fragment_molecule,
                    ],
                    layers=1,
                ),
            )
        else:
            # no fragment was made so use a normal graph
            smirks = TorsionSmirks(
                atoms={fragment_torsion},
                smirks=self._get_new_single_graph_smirks(
                    atoms=fragment_torsion,
                    molecule=fragment_data.fragment_molecule,
                ),
            )
        return smirks

    def generate_fitting_schema(
        self,
        molecule: off.Molecule,
        initial_ff_values: str,
        conformers: int = 5,
        expand_torsion_terms: bool = False,
    ) -> TargetSchema:
        """
        This method will consume a molecule and produce a fitting schema related to that molecule for this target.

        Parameters
        ----------
        molecule: off.Molecule
            The molecule that the fitting schema should be created for.
        initial_ff_values: str
            Where the input values should come from for fitting. Note Forcebalance will apply regularization against them.
        conformers: int, default=5
            The number of input conformers to supply for the torsiondrive.
        expand_torsion_terms: bool, default=False
            If the starting torsion terms given by the initial forcefield should first be expanded to cover all k values or not.

        Notes
        -----
            Due to the clustering of the torsions into new molecule specific smirks patterns the starting values used from a current forcefield may not be correct.
        """
        # the provenance here captures the settings used in the target including the priors.
        target_schema = TargetSchema(target_name=self.name, provenance=self.dict())
        # set up where the initial values will come from
        ff = ForceFieldEditor(forcefield_name=initial_ff_values)

        if self.fragmentation:
            fragments = self._fragment_molecule(molecule)
            # now produce the fitting schema
            for fragment in fragments:
                attributes = fragment.fragment_attributes
                # get all torsions with this central bond
                torsions = self.get_all_torsions(
                    fragment.fragment_torsion, fragment.fragment_molecule
                )
                if fragment.fragment_molecule.n_conformers < conformers:
                    fragment.fragment_molecule.generate_conformers(
                        n_conformers=conformers
                    )
                # make the fitting entry with metadata
                fitting_entry = FittingEntry(
                    name=fragment.fragment_molecule.to_smiles(explicit_hydrogens=False),
                    attributes=attributes,
                    collection_workflow=self.collection_workflow,
                    qc_spec=self.qc_spec,
                    input_conformers=fragment.fragment_molecule.conformers,
                    extras={
                        "dihedrals": [
                            torsions[0],
                        ]
                    },
                    provenance=self.provenance(),
                )
                # for each torsion make a new smirks if required
                if self.generate_bespoke_terms:
                    for fragment_torsion in torsions:
                        smirks = self._generate_bespoke_fragment_smirks(
                            fragment_data=fragment, fragment_torsion=fragment_torsion
                        )
                        # set initial k values to cover all in the target smirks
                        for k in self.parameter_targets[0].k_values:
                            smirks.add_torsion_term(k)
                        # now update the values using the initial values
                        smirks = ff.get_initial_parameters(
                            molecule=fragment.fragment_molecule,
                            smirk=smirks,
                            clear_existing=not expand_torsion_terms,
                        )
                        smirks.parameterize = [
                            f"k{i}" for i, _ in enumerate(smirks.terms, start=1)
                        ]
                        fitting_entry.add_target_smirks(smirks)
                else:
                    # pull the normal parsley terms
                    smirks = self._get_current_smirks(
                        molecule=fragment.fragment_molecule,
                        atoms=torsions,
                        expand_torsion_terms=expand_torsion_terms,
                        forcefield=ff,
                    )
                    for smirk in smirks:
                        fitting_entry.add_target_smirks(smirk)

                target_schema.add_fitting_entry(fitting_entry)

            return target_schema

        else:
            # for each rotatable bond we should generate a torsiondrive
            attributes = get_molecule_cmiles(molecule)
            rotatable_bonds = self.select_rotatable_bonds(molecule)
            if molecule.n_conformers < conformers:
                molecule.generate_conformers(n_conformers=conformers)
            while rotatable_bonds:
                # get a bond
                bond = rotatable_bonds.pop()
                # get all torsions
                torsions = self.get_all_torsions(bond=bond, molecule=molecule)
                fitting_entry = FittingEntry(
                    name=molecule.to_smiles(explicit_hydrogens=False),
                    attributes=attributes,
                    collection_workflow=self.collection_workflow,
                    qc_spec=self.qc_spec,
                    input_conformers=molecule.conformers,
                    extras={
                        "dihedrals": [
                            torsions[0],
                        ]
                    },
                    provenance=self.provenance(),
                )
                # make a new smirks pattern for each dihedral if requested
                if self.generate_bespoke_terms:
                    for torsion in torsions:
                        smirks = TorsionSmirks(
                            atoms={torsion},
                            smirks=self._get_new_single_graph_smirks(
                                atoms=torsion,
                                molecule=molecule,
                            ),
                        )
                        # set initial k values to cover all in the target smirks
                        for k in self.parameter_targets[0].k_values:
                            smirks.add_torsion_term(k)

                        # now update the values using the initial values
                        smirks = ff.get_initial_parameters(
                            molecule=molecule,
                            smirk=smirks,
                            clear_existing=not expand_torsion_terms,
                        )
                        smirks.parameterize = [
                            f"k{i}" for i, _ in enumerate(smirks.terms, start=1)
                        ]
                        fitting_entry.add_target_smirks(smirks)
                else:
                    smirks = self._get_current_smirks(
                        molecule=molecule,
                        atoms=torsions,
                        expand_torsion_terms=expand_torsion_terms,
                        forcefield=ff,
                    )
                    for smirk in smirks:
                        fitting_entry.add_target_smirks(smirk)

                # look for symmetry equivalent torsions
                for smirks in fitting_entry.target_smirks:
                    dihedrals = molecule.chemical_environment_matches(smirks.smirks)
                    # order the data
                    ordered_dihedrals = [
                        dihedral
                        if dihedral[1] < list(reversed(dihedral))[1]
                        else tuple(list(reversed(dihedral)))
                        for dihedral in dihedrals
                    ]
                    # deduplicate dihedrals
                    ordered_dihedrals = set(ordered_dihedrals)
                    # now store all of the torsions
                    smirks.atoms = list(ordered_dihedrals)

                    # now we need to remove all of the rotatable bonds we have hit from the list
                    central_bonds = set(
                        [tuple(sorted(dih[1:3])) for dih in ordered_dihedrals]
                    )
                    for cb in central_bonds:
                        try:
                            rotatable_bonds.remove(cb)
                        except ValueError:
                            continue

                # when adding the fitting entry the smirks are condensed where possible
                target_schema.add_fitting_entry(fitting_entry)

            return target_schema

    def _get_current_smirks(
        self,
        molecule: off.Molecule,
        atoms: List[Tuple[int, int, int, int]],
        expand_torsion_terms: bool,
        forcefield: Union[ForceFieldEditor, str],
    ) -> List[TorsionSmirks]:
        """
        Get the current smirks torsion parameters in bespokefit form and expand the torsion k values when requested.

        Parameters
        ----------
        molecule: off.Molecule
            The molecule which we want the smirks for.
        atoms: List[Tuple[int, int, int, int]]
            The list of atom torsion tuples we want the smirks for.
        expand_torsion_terms: bool
            If the k values should be fully expanded with extra terms set close to zero. By default we expand up to k4.
        forcefield: Union[ForceFieldEditor, str]
            The forcefield that should be used to get the parameters, if this is a string a editor class is made other wise we can use the current class.
        """
        if isinstance(forcefield, str):
            ff = ForceFieldEditor(forcefield_name=forcefield)
        else:
            ff = forcefield
        smirks = ff.get_smirks_parameters(molecule=molecule, atoms=atoms)

        if expand_torsion_terms:
            # for each smirk if there is no k value add a new one
            for smirk in smirks:
                for i in range(5):
                    if str(i) not in smirk.terms:
                        smirk.add_torsion_term(term=str(i))
        # update the parameterize flags
        for smirk in smirks:
            smirk.parameterize = [f"k{i}" for i, _ in enumerate(smirk.terms, start=1)]

        return smirks

    def select_rotatable_bonds(self, molecule: off.Molecule) -> List[Tuple[int, int]]:
        """
        Gather a list of rotatable bonds based on the chosen torsion selection method.

        Parameters
        ----------
        molecule: off.Molecule
            The molecule whoes rotatable bonds we want to find.

        Returns
        -------
        List[Tuple[int, int]]
            A list of central bond atom index tuples.
        """

        if self.torsion_selection == TorsionSelection.NonTerminal:
            ignore_functional_groups = ["[*]~[*:1]-[X2H1,X3H2,X4H3:2]-[#1]"]

        else:
            ignore_functional_groups = None

        bonds = [
            tuple(sorted([bond.atom1_index, bond.atom2_index]))
            for bond in molecule.find_rotatable_bonds(
                ignore_functional_groups=ignore_functional_groups
            )
        ]
        return bonds

    def get_all_torsions(
        self, bond: Tuple[int, int], molecule: off.Molecule
    ) -> List[Tuple[int, int, int, int]]:
        """
        Get all torsions that pass through the central bond to generate smirks patterns.

        Parameters
        ----------
        bond: Tuple[int, int]
            The bond which we want all torsions for.
        molecule: off.Molecule
            The molecule which the bond corresponds to.

        Returns
        -------
        List[Tuple[int, int, int, int]]
            A list of all of the torsion tuples passing through this central bond.
        """

        torsions = []
        central_bond = molecule.get_bond_between(*bond)
        atom1, atom2 = central_bond.atom1, central_bond.atom2

        for atom in atom1.bonded_atoms:
            for end_atom in atom2.bonded_atoms:
                if atom != atom2 and end_atom != atom1:
                    dihedral = (
                        atom.molecule_atom_index,
                        atom1.molecule_atom_index,
                        atom2.molecule_atom_index,
                        end_atom.molecule_atom_index,
                    )
                    torsions.append(dihedral)
                else:
                    continue

        return torsions

    def provenance(self) -> Dict[str, Any]:
        provenance = super().provenance()

        if self.fragmentation:
            import fragmenter
            import openeye

            provenance["fragmenter"] = fragmenter.__version__
            provenance["openeye"] = openeye.__version__

        return provenance

    def prep_for_fitting(self, fitting_target: "TargetSchema") -> None:
        """
        This should be implemented by the specific torsion target classes.
        """
        pass

    def local_reference_collection(
        self, fitting_target: "TargetSchema"
    ) -> "TargetSchema":
        pass

    @classmethod
    def is_available(cls) -> bool:
        try:
            import chemper
            import openeye
            import openforcefield

            return True
        except ImportError:
            return False


class AbInitio_SMIRNOFF(TorsionDrive1D):
    """
    This is an implementation of the specific AbInitio_SMIRNOFF target for ForceBalanace.
    This classes used the fragmentation and 1D torsiondrive collection technique but has specific file converters for forcebalance before fitting.
    """

    name = "AbInitio_SMIRNOFF"
    description = "Static single point energy and gradient fitting."
    keywords: Dict[str, Any] = {
        "writelevel": 1,
        "mol2": "molecule.mol2",
        "pdb": "molecule.pdb",
        "coords": "scan.xyz",
    }

    def prep_for_fitting(self, fitting_target: TargetSchema) -> None:
        """
        Here we convert the targetschema to make the specific files needed by forcebalance for fitting.

        Makes
         - scan.xyz
         - mol2
         - pdb
         - qdata.txt

        Note:
            This function assumes it is already in the `targets` directory and just adds sub directories in place.
        """
        from openforcefield.utils.toolkits import RDKitToolkitWrapper

        if not fitting_target.ready_for_fitting:
            raise MissingReferenceError(
                f"The fitting target could not be fit due to missing reference data: {fitting_target.dict()}"
            )

        home = os.getcwd()
        for entry in fitting_target.entries:
            # we need to make a new folder for this entry
            os.mkdir(entry.name)
            os.chdir(entry.name)
            # now we need to make all of the input files
            molecule = entry.current_molecule
            # we only want one conformer here
            molecule.generate_conformers(n_conformers=1, clear_existing=True)
            molecule.assign_partial_charges("am1-mulliken")
            molecule.to_file("molecule.mol2", "mol2")
            molecule.to_file(
                file_path="molecule.pdb",
                file_format="pdb",
                toolkit_registry=RDKitToolkitWrapper(),
            )
            # remove the conformers
            molecule._conformers = []
            for result in entry.get_reference_data():
                geometry = unit.Quantity(result.molecule.geometry, unit=unit.bohrs)
                molecule.add_conformer(geometry)
            molecule.to_file("scan.xyz", "xyz")
            # now make the qdata file
            self.create_qdata(
                entry.get_reference_data(),
                fit_gradient=fitting_target.provenance.get("fit_gradient", False),
            )
            # move back to the home dir
            os.chdir(home)

    def create_qdata(
        self, data: List[SingleResult], fit_gradient: bool = False
    ) -> None:
        """
        This function creates the qdata.txt file in place using the list of single results and will optionally include
        the gradient data.
        """

        # loop over the results in order and write out the coords and energies also gradient if requested
        with open("qdata.txt", "w") as qdata:
            for i, result in enumerate(data):
                qdata.write(f"JOB {i}\n")
                coords = unit.Quantity(
                    result.molecule.geometry, unit=unit.bohrs
                ).in_units_of(unit.angstrom)
                qdata.write(
                    f"COORDS  {'  '.join(str(i) for i in  coords.flatten().tolist())}\n"
                )
                qdata.write(f"ENERGY {result.energy}\n")
                if fit_gradient:
                    qdata.write(
                        f"GRADIENT  {'  '.join(str(i) for i in  result.gradient.flatten().tolist())}\n"
                    )
                qdata.write("\n")


class TorsionProfile_SMIRNOFF(AbInitio_SMIRNOFF):
    """
    This is an implementation of the specific TorsionProfile_SMIRNOFF target in Forcebalance which is adjusted to make the correct input files.
    """

    name = "TorsionProfile_SMIRNOFF"
    description = "Single point energy and gradient fitting with constrained relaxation, for torsiondrives only."
    keywords: Dict[str, Any] = {
        "writelevel": 2,
        "mol2": "molecule.mol2",
        "pdb": "molecule.pdb",
        "coords": "scan.xyz",
        "attenuate": None,
        "energy_denom": 1.0,
        "energy_upper": 5.0,
        "openmm_platform": "Reference",
    }

    def make_scan_metadata(self, entry: FittingEntry) -> None:
        """
        Create the metadata.json needed for the constrained optimizations.
        """
        # move to the directory which has already been made
        json_data = {
            "dihedrals": entry.extras["dihedrals"],
            "grid_spacing": self.grid_spacings,
            "dihedral_ranges": None,
            "energy_decrease_thresh": None,
            "energy_upper_limit": self.energy_upper_limit,
            "attributes": entry.attributes,
            "torsion_grid_ids": [
                data.extras["dihedral_angle"] for data in entry.get_reference_data()
            ],
        }
        # now write to file
        serialize(json_data, os.path.join(entry.name, "metadata.json"))

    def prep_for_fitting(self, fitting_target: TargetSchema) -> None:
        """
        Call the super then add the scan metadata.
        """

        super().prep_for_fitting(fitting_target)
        for entry in fitting_target.entries:
            self.make_scan_metadata(entry)
