"""
Tools for dealing with SMIRNOFF force field manipulation.
"""
import copy
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Tuple, Union

import numpy as np
from openff.toolkit import Molecule
from openff.toolkit.typing.engines.smirnoff import (
    AngleHandler,
    BondHandler,
    ForceField,
    ImproperTorsionHandler,
    ParameterType,
    ProperTorsionHandler,
    vdWHandler,
)
from openff.toolkit.utils.exceptions import ParameterLookupError

if TYPE_CHECKING:
    from openff.bespokefit.schema.smirnoff import SMIRNOFFParameter

_PARAMETER_TYPE_TO_HANDLER = {
    vdWHandler.vdWType: "vdW",
    BondHandler.BondType: "Bonds",
    AngleHandler.AngleType: "Angles",
    ProperTorsionHandler.ProperTorsionType: "ProperTorsions",
    ImproperTorsionHandler.ImproperTorsionType: "ImproperTorsions",
}


class SMIRKSType(str, Enum):
    Bonds = "Bonds"
    Angles = "Angles"
    ProperTorsions = "ProperTorsions"
    ImproperTorsions = "ImproperTorsions"
    Vdw = "vdW"


class ForceFieldEditor:
    def __init__(self, force_field: Union[str, ForceField]):
        """

        Args:
            force_field: A path to a serialized SMIRNOFF force field or the
                contents of an OFFXML serialized SMIRNOFF force field.

        Notes
            * This will always try to strip the constraints parameter handler as the FF
              should be unconstrained for fitting.
        """

        if isinstance(force_field, ForceField):
            self.force_field = force_field
        else:
            self.force_field = ForceField(force_field, allow_cosmetic_attributes=True)

        try:
            # try and strip a constraint handler
            self.force_field.deregister_parameter_handler("Constraints")
        except KeyError:
            pass

    def add_parameters(self, parameters: List[ParameterType]) -> List[ParameterType]:
        """
        Work out which type of smirks this is and add it to the forcefield, if this is
        not a bespoke parameter update the value in the forcefield.
        """

        _smirks_ids = {
            BondHandler.BondType: "b",
            AngleHandler.AngleType: "a",
            ProperTorsionHandler.ProperTorsionType: "t",
            vdWHandler.vdWType: "n",
        }

        parameters_by_handler = dict()

        for parameter in parameters:

            handler_type = _PARAMETER_TYPE_TO_HANDLER[parameter.__class__]
            parameters_by_handler.setdefault(handler_type, []).append(parameter)

        added_parameters = []

        for handler_type, handler_parameters in parameters_by_handler.items():

            current_params = self.force_field[handler_type].parameters
            n_params = len(current_params)

            for i, parameter in enumerate(handler_parameters, start=2):

                parameter_data = parameter.to_dict(discard_cosmetic_attributes=False)

                try:
                    current_param = current_params[parameter_data["smirks"]]
                    parameter_data["id"] = current_param.id
                    # update the parameter using the init to get around conditional
                    # assigment
                    current_param.__init__(
                        **parameter_data, allow_cosmetic_attributes=True
                    )
                except ParameterLookupError:
                    parameter_data["id"] = _smirks_ids[parameter.__class__] + str(
                        n_params + i
                    )

                    current_param = parameter.__class__(
                        **parameter_data, allow_cosmetic_attributes=True
                    )
                    current_params.append(current_param)

                added_parameters.append(current_param)

        return added_parameters

    def label_molecule(
        self, molecule: Molecule
    ) -> Dict[str, Dict[Tuple[int, ...], ParameterType]]:
        """
        Type the molecule with the forcefield and return a molecule parameter dictionary.

        Args:
            molecule: The molecule that should be labeled by the force field.

        Returns:
            A dictionary of each parameter assigned to molecule organised by parameter
            handler type.
        """
        return self.force_field.label_molecules(molecule.to_topology())[0]

    def get_parameters(
        self, molecule: Molecule, atoms_by_type: Dict[str, List[Tuple[int, ...]]]
    ) -> List[ParameterType]:
        """
        For a given molecule label it and get back the smirks patterns and parameters
        for the requested atoms.
        """

        off_params = {}

        labels = self.label_molecule(molecule=molecule)

        for parameter_type, atom_ids in atoms_by_type.items():
            for atoms in atom_ids:
                # now we can get the handler type using the smirk type
                off_param = labels[parameter_type][atoms]
                # get a unique list of openff params as some params may hit many atoms
                off_params[(off_param.__class__, off_param.smirks)] = off_param

        return [*off_params.values()]

    def get_initial_parameters(
        self,
        molecule: Molecule,
        smirks: List["SMIRNOFFParameter"],
    ) -> List[ParameterType]:
        """
        Find the initial parameters assigned to the atoms in the given smirks patterns
        and update the values to match the force field.
        """
        labels = self.label_molecule(molecule=molecule)

        initial_parameters = []

        # now find the atoms
        for smirks_pattern in smirks:

            matches = molecule.chemical_environment_matches(query=smirks_pattern.smirks)

            if len(matches) == 0:
                continue

            parameters = labels[smirks_pattern.type]

            if (
                smirks_pattern.type == "ProperTorsions"
                or smirks_pattern.type == "ImproperTorsions"
            ):

                # here we can combine multiple parameter types
                # TODO is this needed?
                openff_params = [parameters[match] for match in matches]

                n_terms = [len(param.k) for param in openff_params]

                # Choose the torsion parameter that has the most k values as the
                # starting point.
                match = matches[np.argmax(n_terms)]

            else:

                match = matches[0]

            initial_parameter = copy.deepcopy(parameters[match])
            initial_parameter.smirks = smirks_pattern.smirks
            # mark the parameter as being bespokefit
            if not initial_parameter.id.endswith("-BF"):
                initial_parameter.id += "-BF"

            initial_parameters.append(initial_parameter)

        return initial_parameters
