"""
Tools for dealing with forcefield manipulation.
"""

from typing import Dict, List, Union

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
        """
        self.forcefield = ForceField(forcefield_name, allow_cosmetic_attributes=True)

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
            for i, parameter in enumerate(parameters):
                parameter["id"] = f"t{no_params + i}"
                current_params.insert(-1, _smirks_conversion[smirk_type](**parameter))

    def label_molecule(self, molecule: off.Molecule) -> Dict[str, str]:
        """
        Type the molecule with the forcefield and return a molecule parameter dictionary.
        """
        return self.forcefield.label_molecules(molecule.to_topology())[0]

    def update_smirks_parameters(
        self, smirks: List[Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]]
    ) -> List[Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]]:
        """
        Take a list of input smirks parameters and update the values of the parameters using the forcefield.
        """
        # first group them then extract the parameters and transfer back.
        # should work for all parameters we may need a special method for torsions.
        pass
