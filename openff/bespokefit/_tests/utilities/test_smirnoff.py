"""
Test the force field editing tools.
"""

import copy
import os

import numpy as np
from openff.toolkit.topology import Molecule
from openff.units import unit
from openff.utilities import get_data_file_path

from openff.bespokefit.schema.smirnoff import (
    AngleSMIRKS,
    BondSMIRKS,
    ProperTorsionSMIRKS,
    VdWSMIRKS,
)
from openff.bespokefit.utilities.smirnoff import ForceFieldEditor


def test_loading_force_fields():
    """
    Test that loading the forcefield always strips out any constraints.
    """

    # load in the initial FF with constraints
    ff = ForceFieldEditor(force_field="openff-1.0.0.offxml")
    assert "Constraints" not in ff.force_field.registered_parameter_handlers


def test_adding_new_smirks_types():
    """Test adding new smirks to a force field."""

    ff = ForceFieldEditor(force_field="openff-1.0.0.offxml")

    existing_parameter = copy.deepcopy(ff.force_field["vdW"].parameters["[#6X2:1]"])
    existing_parameter.rmin_half *= 2.0

    new_parameter = copy.deepcopy(existing_parameter)
    new_parameter.smirks = "[#30:1]"
    new_parameter.rmin_half = 123.0 * unit.angstrom
    assert new_parameter.smirks not in ff.force_field["vdW"].parameters

    updated_parameters = ff.add_parameters([existing_parameter, new_parameter])
    assert len(updated_parameters) == 2

    assert new_parameter.smirks in ff.force_field["vdW"].parameters
    assert np.isclose(
        ff.force_field["vdW"]
        .parameters[new_parameter.smirks]
        .rmin_half.m_as(unit.angstrom),
        123.0,
    )
    assert np.isclose(
        ff.force_field["vdW"]
        .parameters[existing_parameter.smirks]
        .rmin_half.m_as(unit.angstrom),
        existing_parameter.rmin_half.m_as(unit.angstrom),
    )


def test_label_molecule():
    """Test that labeling a molecule with the editor works."""

    ff = ForceFieldEditor(force_field="openff-1.0.0.offxml")

    ethane = Molecule.from_file(
        file_path=get_data_file_path(
            os.path.join("test", "molecules", "ethane.sdf"), "openff.bespokefit"
        ),
        file_format="sdf",
    )

    labels = ff.label_molecule(molecule=ethane)

    for param_type in ["Bonds", "Angles", "ProperTorsions", "ImproperTorsions", "vdW"]:
        assert param_type in labels


def test_get_parameters():
    ff = ForceFieldEditor(force_field="openff-1.0.0.offxml")
    molecule = Molecule.from_mapped_smiles("[H:1]-[C:2]#[C:3]-[H:4]")

    parameters = ff.get_parameters(
        molecule=molecule,
        atoms_by_type={
            "vdW": [(0,), (1,), (2,), (3,)],
            "Bonds": [(0, 1), (1, 2), (2, 3)],
            "Angles": [(0, 1, 2), (1, 2, 3)],
            "ProperTorsions": [(0, 1, 2, 3)],
        },
    )

    assert len(parameters) == 6

    assert {parameter.smirks for parameter in parameters} == {
        "[#1:1]-[#6X2]",
        "[#6X2:1]",
        "[#6X2:1]-[#1:2]",
        "[#6X2:1]#[#6X2:2]",
        "[*:1]~[#6X2:2]~[*:3]",
        "[*:1]-[*:2]#[*:3]-[*:4]",
    }


def test_get_initial_parameters():
    molecule = Molecule.from_mapped_smiles("[H:1]-[C:2]#[C:3]-[H:4]")
    smirks = [
        VdWSMIRKS(smirks="[#6:1]", attributes=set()),
        BondSMIRKS(smirks="[#6:1]~[#6:2]", attributes=set()),
        BondSMIRKS(smirks="[#17:1]-[#1:2]", attributes=set()),
        AngleSMIRKS(smirks="[*:1]~[#6:2]~[#6:3]", attributes=set()),
        ProperTorsionSMIRKS(smirks="[#1:1]~[#6:2]~[#6:3]~[#1:4]", attributes=set()),
    ]

    ff = ForceFieldEditor(force_field="openff-1.0.0.offxml")

    initial_parameters = {
        parameter.smirks: parameter
        for parameter in ff.get_initial_parameters(molecule, smirks)
    }

    expected_values = {
        "[#6:1]": ("vdW", "[#6X2:1]"),
        "[#6:1]~[#6:2]": ("Bonds", "[#6X2:1]#[#6X2:2]"),
        "[*:1]~[#6:2]~[#6:3]": ("Angles", "[*:1]~[#6X2:2]~[*:3]"),
        "[#1:1]~[#6:2]~[#6:3]~[#1:4]": ("ProperTorsions", "[*:1]-[*:2]#[*:3]-[*:4]"),
    }

    assert len(initial_parameters) == len(expected_values)

    for new_smirks, (handler_type, old_smirks) in expected_values.items():
        new_parameter = initial_parameters[new_smirks].to_dict()
        old_parameter = ff.force_field[handler_type].parameters[old_smirks].to_dict()

        for key in new_parameter:
            if not isinstance(new_parameter[key], unit.Quantity):
                continue

            new_value = new_parameter[key].m_as(old_parameter[key].units)
            old_value = old_parameter[key].m_as(old_parameter[key].units)

            assert np.isclose(new_value, old_value)
