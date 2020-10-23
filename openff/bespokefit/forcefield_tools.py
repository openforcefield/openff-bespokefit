"""
Tools for dealing with forcefield manipulation.
"""

from typing import Dict, Iterable, List, Union

from openforcefield import topology as off
from openforcefield.typing.engines.smirnoff import (
    AngleHandler,
    BondHandler,
    ForceField,
    ProperTorsionHandler,
    vdWHandler,
)

from .common_structures import SmirksType
from .schema.smirks import AngleSmirks, AtomSmirks, BondSmirks, TorsionSmirks


class ForceFieldEditor:
    def __init__(self, forcefield_name: str):
        """
        Gather the forcefield ready for manipulation.

        Parameters
        ----------
        forcefield_name: str
            The string of the target forcefield path.

        Notes
        ------
            This will always try to strip the constraints parameter handler as the FF should be unconstrained for fitting.
        """
        self.forcefield = ForceField(forcefield_name, allow_cosmetic_attributes=True)

        # try and strip a constraint handler
        try:
            del self.forcefield._parameter_handlers["Constraints"]
        except KeyError:
            pass

    def add_smirks(
        self,
        smirks: List[Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]],
        parameterize: bool = True,
    ) -> None:
        """
        Work out which type of smirks this is and add it to the forcefield.
        """

        _smirks_conversion = {
            SmirksType.Bonds: BondHandler.BondType,
            SmirksType.Angles: AngleHandler.AngleType,
            SmirksType.ProperTorsions: ProperTorsionHandler.ProperTorsionType,
            SmirksType.Vdw: vdWHandler.vdWType,
        }
        _smirks_ids = {
            SmirksType.Bonds.value: "b",
            SmirksType.Angles.value: "a",
            SmirksType.ProperTorsions.value: "t",
            SmirksType.Vdw.value: "n",
        }
        new_params = {}

        for smirk in smirks:
            smirk_data = smirk.to_off_smirks()
            if not parameterize:
                del smirk_data["parameterize"]
            new_params.setdefault(smirk.type.value, []).append(smirk_data)

        for smirk_type, parameters in new_params.items():
            current_params = self.forcefield.get_parameter_handler(
                smirk_type
            ).parameters
            no_params = len(current_params)
            for i, parameter in enumerate(parameters, start=1):
                parameter["id"] = _smirks_ids[smirk_type] + str(no_params + i)
                current_params.insert(-1, _smirks_conversion[smirk_type](**parameter))

    def label_molecule(self, molecule: off.Molecule) -> Dict[str, str]:
        """
        Type the molecule with the forcefield and return a molecule parameter dictionary.

        Parameters
        ----------
        molecule: off.Molecule
            The openforcefield.topology.Molecule that should be labeled by the forcefield.

        Returns
        -------
        Dict[str, str]
            A dictionary of each parameter assigned to molecule organised by parameter handler type.
        """
        return self.forcefield.label_molecules(molecule.to_topology())[0]

    def update_smirks_parameters(
        self,
        smirks: Iterable[Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]],
    ) -> None:
        """
        Take a list of input smirks parameters and update the values of the parameters using the given forcefield in place.

        Parameters
        ----------
        smirks : Iterable[Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]]
            An iterable containing smirks schemas that are to be updated.

        """

        for smirk in smirks:
            new_parameter = self.forcefield.get_parameter_handler(
                smirk.type.value
            ).parameters[smirk.smirks]
            # now we just need to update the smirks with the new values
            smirk.update_parameters(off_smirk=new_parameter)
