"""
Tools for dealing with SMIRNOFF force field manipulation.
"""

from typing import Dict, Iterable, List, Tuple, Union

from openforcefield import topology as off
from openforcefield.typing.engines.smirnoff import (
    AngleHandler,
    BondHandler,
    ForceField,
    ImproperTorsionHandler,
    ParameterLookupError,
    ProperTorsionHandler,
    vdWHandler,
)

from openff.bespokefit.schema.bespoke.smirks import (
    BespokeAngleSmirks,
    BespokeAtomSmirks,
    BespokeBondSmirks,
    BespokeSmirksParameter,
    BespokeTorsionSmirks,
)
from openff.bespokefit.schema.smirnoff import SmirksType


def smirks_from_off(
    off_smirks: Union[
        AngleHandler.AngleType,
        vdWHandler.vdWType,
        BondHandler.BondType,
        ProperTorsionHandler.ProperTorsionType,
        ImproperTorsionHandler.ImproperTorsionType,
    ]
) -> BespokeSmirksParameter:
    """Build and Bespokefit smirks parameter object from the openforcefield toolkit
    equivalent object.
    """

    # map the off types to the bespoke types
    _off_to_smirks = {
        "Angle": BespokeAngleSmirks,
        "Atom": BespokeAtomSmirks,
        "Bond": BespokeBondSmirks,
        "ProperTorsion": BespokeTorsionSmirks,
        "ImproperTorsion": BespokeTorsionSmirks,
    }
    # build the smirks and update it
    smirk = _off_to_smirks[off_smirks._VALENCE_TYPE].from_off_smirks(
        off_smirk=off_smirks
    )
    return smirk


class ForceFieldEditor:
    def __init__(self, force_field_name: str):
        """
        Gather the forcefield ready for manipulation.

        Parameters
        ----------
        force_field_name: str
            The string of the target forcefield path.

        Notes
        ------
            This will always try to strip the constraints parameter handler as the FF
            should be unconstrained for fitting.
        """
        self.force_field = ForceField(force_field_name, allow_cosmetic_attributes=True)

        # try and strip a constraint handler
        try:
            del self.force_field._parameter_handlers["Constraints"]
        except KeyError:
            pass

    def add_smirks(
        self,
        smirks: List[BespokeSmirksParameter],
        parameterize: bool = True,
    ) -> None:
        """
        Work out which type of smirks this is and add it to the forcefield, if this is
        not a bespoke parameter update the value in the forcefield.
        """

        _smirks_conversion = {
            SmirksType.Bonds: BondHandler.BondType,
            SmirksType.Angles: AngleHandler.AngleType,
            SmirksType.ProperTorsions: ProperTorsionHandler.ProperTorsionType,
            SmirksType.Vdw: vdWHandler.vdWType,
        }
        _smirks_ids = {
            SmirksType.Bonds: "b",
            SmirksType.Angles: "a",
            SmirksType.ProperTorsions: "t",
            SmirksType.Vdw: "n",
        }
        new_params = {}
        for smirk in smirks:
            if smirk.type not in new_params:
                new_params[smirk.type] = [
                    smirk,
                ]
            else:
                if smirk not in new_params[smirk.type]:
                    new_params[smirk.type].append(smirk)

        for smirk_type, parameters in new_params.items():
            current_params = self.force_field.get_parameter_handler(
                smirk_type
            ).parameters
            no_params = len(current_params)
            for i, parameter in enumerate(parameters, start=2):
                smirk_data = parameter.to_off_smirks()
                if not parameterize:
                    del smirk_data["parameterize"]
                # check if the parameter is new
                try:
                    current_param = current_params[parameter.smirks]
                    smirk_data["id"] = current_param.id
                    # update the parameter using the init to get around conditional
                    # assigment
                    current_param.__init__(**smirk_data)
                except ParameterLookupError:
                    smirk_data["id"] = _smirks_ids[smirk_type] + str(no_params + i)
                    current_params.append(_smirks_conversion[smirk_type](**smirk_data))

    def label_molecule(self, molecule: off.Molecule) -> Dict[str, str]:
        """
        Type the molecule with the forcefield and return a molecule parameter dictionary.

        Parameters
        ----------
        molecule: off.Molecule
            The openforcefield.topology.Molecule that should be labeled by the
            forcefield.

        Returns
        -------
        Dict[str, str]
            A dictionary of each parameter assigned to molecule organised by parameter
            handler type.
        """
        return self.force_field.label_molecules(molecule.to_topology())[0]

    def get_smirks_parameters(
        self, molecule: off.Molecule, atoms: List[Tuple[int, ...]]
    ) -> List[BespokeSmirksParameter]:
        """
        For a given molecule label it and get back the smirks patterns and parameters
        for the requested atoms.
        """
        _atoms_to_params = {
            1: SmirksType.Vdw,
            2: SmirksType.Bonds,
            3: SmirksType.Angles,
            4: SmirksType.ProperTorsions,
        }
        smirks = []
        labels = self.label_molecule(molecule=molecule)
        for atom_ids in atoms:
            # work out the parameter type from the length of the tuple
            smirk_class = _atoms_to_params[len(atom_ids)]
            # now we can get the handler type using the smirk type
            off_param = labels[smirk_class.value][atom_ids]
            smirk = smirks_from_off(off_smirks=off_param)
            smirk.atoms.add(atom_ids)
            if smirk not in smirks:
                smirks.append(smirk)
            else:
                # update the covered atoms
                index = smirks.index(smirk)
                smirks[index].atoms.add(atom_ids)
        return smirks

    def update_smirks_parameters(
        self,
        smirks: Iterable[BespokeSmirksParameter],
    ) -> None:
        """
        Take a list of input smirks parameters and update the values of the parameters
        using the given forcefield in place.

        Parameters
        ----------
        smirks : Iterable[Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]]
            An iterable containing smirks schemas that are to be updated.

        """

        for smirk in smirks:
            new_parameter = self.force_field.get_parameter_handler(
                smirk.type
            ).parameters[smirk.smirks]
            # now we just need to update the smirks with the new values
            smirk.update_parameters(off_smirk=new_parameter)

    def get_initial_parameters(
        self,
        molecule: off.Molecule,
        smirks: List[BespokeSmirksParameter],
        clear_existing: bool = True,
    ) -> List[BespokeSmirksParameter]:
        """
        Find the initial parameters assigned to the atoms in the given smirks pattern
        and update the values to match the forcefield.
        """
        labels = self.label_molecule(molecule=molecule)
        # now find the atoms
        for smirk in smirks:
            parameters = labels[smirk.type]
            if smirk.type == SmirksType.ProperTorsions:
                # here we can combine multiple parameter types
                # TODO is this needed?
                openff_params = []
                for atoms in smirk.atoms:
                    param = parameters[atoms]
                    openff_params.append(param)

                # now check if they are different types
                types = set([param.id for param in openff_params])

                # now update the parameter
                smirk.update_parameters(
                    off_smirk=openff_params[0], clear_existing=clear_existing
                )
                # if there is more than expand the k terms
                if len(types) > 1:
                    for param in openff_params[1:]:
                        smirk.update_parameters(param, clear_existing=False)
            else:
                atoms = list(smirk.atoms)[0]
                param = parameters[atoms]
                smirk.update_parameters(off_smirk=param, clear_existing=True)

        return smirks
