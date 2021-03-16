import abc
from typing import TYPE_CHECKING, Dict, List, Optional, Union

from openforcefield.topology import Molecule
from openforcefield.typing.engines.smirnoff import ForceField
from pydantic import Field
from typing_extensions import Literal

from openff.bespokefit.exceptions import OptimizerError
from openff.bespokefit.schema.bespoke.smirks import (
    BespokeSmirksParameter,
    BespokeTorsionSmirks,
)
from openff.bespokefit.schema.bespoke.tasks import TorsionTask
from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationSchema,
    Status,
)
from openff.bespokefit.schema.smirnoff import SmirksType
from openff.bespokefit.utilities.pydantic import SchemaBase

if TYPE_CHECKING:
    from openff.bespokefit.utilities.smirnoff import ForceFieldEditor

OptimizationSchemaType = Union[OptimizationSchema, BespokeOptimizationSchema]


class BaseOptimizationResults(SchemaBase, abc.ABC):
    """The base class for data models which store the results of an optimization."""

    type: Literal["base"] = "base"

    input_schema: Optional[OptimizationSchemaType] = Field(
        None, description="The schema defining the input to the optimization."
    )
    provenance: Dict[str, str] = Field(
        ..., description="The versions of the software used to generate the results."
    )

    status: Status = Field(
        Status.Undefined, description="The status of the optimization."
    )

    # TODO: Other fields which would be good to include.

    # objective_function: List[float] = Field(
    #     ..., description="The value of the objective function at each iteration."
    # )


class OptimizationResults(BaseOptimizationResults):
    """A class for storing the results of a general force field optimization."""

    type: Literal["general"] = "general"

    refit_force_field: Optional[str] = Field(
        None, description="The XML contents of the refit force field."
    )

    # TODO: Store the actual molecule attributes


class BespokeOptimizationResults(BaseOptimizationResults):
    """A class for storing the results of a bespoke force field optimization."""

    type: Literal["bespoke"] = "bespoke"

    final_smirks: List[BespokeSmirksParameter] = Field(
        [],
        description="A list of the refit force field parameters.",
    )

    def get_final_force_field(
        self,
        generate_bespoke_terms: bool = True,
        drop_out_value: Optional[float] = None,
    ) -> ForceField:
        """
        Generate the final bespoke forcefield for this molecule by collecting together
        all optimized smirks.

        Note:
            It is know that when creating fitting smirks for the fragments that they can
            hit unintended dihedrals in other fragments if they are similar during
            fitting. To ensure the correct parameters are used in their intended
            positions on the parent molecule each fragment is typed with the fitting
            force field and parameters again and a new bespoke term for the parent is
            made which uses the same parameters.

        Parameters:
            generate_bespoke_terms: If molecule specific bespoke terms should be made,
                this is recommended as some fragment smirks patterns may not transfer
                back to the parent correctly due to fragmentation.
            drop_out_value: Any torsion force constants below this value will be dropped
                as they are probably negligible.
        """
        from openff.bespokefit.utilities.smirnoff import ForceFieldEditor

        # TODO change this to a util function remove from target base class
        # check that all optimizations are finished
        if self.status != Status.Complete:

            raise OptimizerError(
                "The molecule has not completed all optimization stages which are "
                "required to generate the final force field."
            )

        if self.final_smirks is None:
            raise OptimizerError(
                "The optimization status is complete but no optimized smirks were "
                "found."
            )

        # get all of the target smirks
        target_smirks = self.final_smirks
        # build the parent molecule
        parent_molecule = self.input_schema.target_molecule.molecule

        if drop_out_value is not None:
            # loop over all of the target smirks and drop and torsion k values lower
            # than the drop out
            for smirk in target_smirks:

                if smirk.type == SmirksType.ProperTorsions:
                    # keep a list of terms to remove
                    to_remove = []

                    for p, term in smirk.terms.items():
                        if abs(float(term.k.split("*")[0])) < drop_out_value:
                            to_remove.append(p)

                    # now remove the low values
                    for p in to_remove:
                        del smirk.terms[p]

        # the final fitting force field should have all final smirks propagated through
        fitting_ff = ForceFieldEditor(
            force_field_name=self.input_schema.initial_force_field
        )
        fitting_ff.add_smirks(smirks=target_smirks, parameterize=False)

        # here we type the fragment with the final forcefield and then build a bespoke
        # dihedral term for the parent to hit the atoms that map from the fragment to
        # the parent we do not modify any other smirks types but this needs testing to
        # make sure that they do transfer.
        if generate_bespoke_terms:
            bespoke_smirks = []
            # get a list of unique fragments and all of the torsions that have been
            # targeted
            for target in self.input_schema.targets:
                if target.bespoke_task_type() == "torsion1d":
                    for task in target.reference_data.tasks:
                        # check if the smirks are from a fragment
                        if task.fragment:
                            new_smirks = self._generate_bespoke_torsions(
                                force_field=fitting_ff,
                                parent_molecule=parent_molecule,
                                task_data=task,
                            )
                            bespoke_smirks.extend(new_smirks)

            # make a new ff object with the new terms
            bespoke_ff = ForceFieldEditor(
                force_field_name=self.input_schema.initial_force_field
            )
            # get a list of non torsion smirks
            new_smirks = [
                smirk
                for smirk in target_smirks
                if smirk.type != SmirksType.ProperTorsions
            ]
            new_smirks.extend(bespoke_smirks)
            bespoke_ff.add_smirks(smirks=new_smirks, parameterize=False)
            return bespoke_ff.force_field

        else:
            return fitting_ff.force_field

    def _generate_bespoke_torsions(
        self,
        force_field: "ForceFieldEditor",
        parent_molecule: Molecule,
        task_data: TorsionTask,
    ) -> List[BespokeTorsionSmirks]:
        """For the given task generate set of bespoke torsion terms for the parent
        molecule using all layers. Here we have to type the fragment and use the fragment
        parent mapping to transfer the parameters.
        """
        from openff.bespokefit.bespoke.smirks import SmirksGenerator

        smirks_gen = SmirksGenerator(
            target_smirks=[SmirksType.ProperTorsions],
            layers="all",
            expand_torsion_terms=False,
        )

        fragment = task_data.graph_molecule
        fragment_parent_mapping = task_data.fragment_parent_mapping
        # label the fitting molecule
        labels = force_field.label_molecule(molecule=fragment)["ProperTorsions"]

        bespoke_torsions = []
        for bond in task_data.central_bonds:
            fragment_dihedrals = smirks_gen.get_all_torsions(
                bond=bond, molecule=fragment
            )
            for dihedral in fragment_dihedrals:
                # get the smirk that hit this torsion
                off_smirk = labels[dihedral]
                # work out the parent torsion
                parent_torsion = tuple([fragment_parent_mapping[i] for i in dihedral])
                # make the bespoke smirks
                smirks = smirks_gen._get_new_single_graph_smirks(
                    atoms=parent_torsion, molecule=parent_molecule
                )
                # make the new Torsion Smirks
                bespoke_smirk = BespokeTorsionSmirks(smirks=smirks)
                bespoke_smirk.update_parameters(off_smirk=off_smirk)
                if bespoke_smirk not in bespoke_torsions:
                    bespoke_torsions.append(bespoke_smirk)

        return bespoke_torsions
