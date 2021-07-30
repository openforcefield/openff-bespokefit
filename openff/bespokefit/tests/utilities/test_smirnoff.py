"""
Test the forcefield editing tools.
"""
import os

import pytest
from openff.qcsubmit.testing import temp_directory
from openff.toolkit.topology import Molecule
from openff.toolkit.typing.engines.smirnoff import ForceField, SMIRNOFFSpecError
from openff.utilities import get_data_file_path

from openff.bespokefit.schema.bespoke.smirks import (
    BespokeAngleSmirks,
    BespokeAtomSmirks,
    BespokeBondSmirks,
    BespokeTorsionSmirks,
    BespokeTorsionTerm,
)
from openff.bespokefit.utilities.smirnoff import ForceFieldEditor


def test_loading_force_fields():
    """
    Test that loading the forcefield always strips out any constraints.
    """

    # load in the initial FF with constraints
    ff = ForceFieldEditor(force_field_name="openff-1.0.0.offxml")

    with temp_directory():
        # write out the ff
        ff.force_field.to_file(filename="bespoke.offxml")
        # read the file and look for the constraints tag
        new_ff = ForceField("bespoke.offxml")
        assert "Constraints" not in new_ff._parameter_handlers


@pytest.mark.parametrize(
    "smirks",
    [
        pytest.param(
            (
                BespokeAtomSmirks(
                    smirks="[#5:1]",
                    parameterize={"rmin_half"},
                    atoms={(0,)},
                    epsilon=0.01,
                    rmin_half=3,
                ),
                "n",
            ),
            id="Atom smirks",
        ),
        pytest.param(
            (
                BespokeBondSmirks(
                    smirks="[#5:1]-[#5:2]",
                    parameterize={"k"},
                    atoms={(0, 1)},
                    k=100,
                    length=2,
                ),
                "b",
            ),
            id="Bond smirks",
        ),
        pytest.param(
            (
                BespokeAngleSmirks(
                    smirks="[#5:1]-[#5:2]-[#1:3]",
                    parameterize={"angle"},
                    atoms={(0, 1, 2)},
                    k=100,
                    angle=120,
                ),
                "a",
            ),
            id="Angle smirks",
        ),
        pytest.param(
            (
                BespokeTorsionSmirks(
                    smirks="[#1:1]-[#5:2]-[#5:3]-[#1:4]",
                    parameterize={"k1"},
                    atoms={(0, 1, 2, 3)},
                    terms={"1": BespokeTorsionTerm(periodicity=1)},
                ),
                "t",
            ),
            id="Torsion smirks",
        ),
    ],
)
def test_adding_new_smirks_types(smirks):
    """
    Test adding new smirks to a forcefield with and without the parameterize flag.
    """

    param, param_id = smirks
    ff = ForceFieldEditor("openff-1.0.0.offxml")
    # now make some new smirks pattern
    ff.add_smirks(smirks=[param], parameterize=True)
    # now make sure it was added under the correct parameter handler
    with temp_directory():
        ff.force_field.to_file(filename="bespoke.offxml")

        new_ff = ForceField("bespoke.offxml", allow_cosmetic_attributes=True)
        parameter = new_ff.get_parameter_handler(param.type.value).parameters[
            param.smirks
        ]
        param_dict = parameter.__dict__
        assert param_dict["_cosmetic_attribs"] == ["parameterize"]
        assert set(param_dict["_parameterize"].split()) == param.parameterize
        # make sure the id is correct
        assert param_id in parameter.id


def test_adding_params_parameterize_flag():
    """
    Test adding new smirks patterns with cosmetic attributes.
    """

    ff = ForceFieldEditor(force_field_name="openff-1.0.0.offxml")
    # add an atom smirks for boron
    boron = BespokeAtomSmirks(
        smirks="[#5:1]",
        parameterize={"epsilon"},
        atoms={(0,)},
        epsilon=0.04,
        rmin_half=3,
    )
    # add boron with the flag
    ff.add_smirks(
        smirks=[
            boron,
        ],
        parameterize=True,
    )
    with temp_directory():
        ff.force_field.to_file(filename="boron.offxml")

        # this should fail if the flag was added
        with pytest.raises(SMIRNOFFSpecError):
            _ = ForceField("boron.offxml", allow_cosmetic_attributes=False)

        boron_ff = ForceField("boron.offxml", allow_cosmetic_attributes=True)
        # now look for the parameter we added
        boron_param = boron_ff.get_parameter_handler("vdW").parameters["[#5:1]"]
        # now make sure it has the param flag
        param_dict = boron_param.__dict__
        assert param_dict["_cosmetic_attribs"] == ["parameterize"]
        assert param_dict["_parameterize"] == "epsilon"


def test_adding_params_no_flag():
    """
    Test adding new smirks patterns with out cosmetic attributes.
    """
    ff = ForceFieldEditor(force_field_name="openff-1.0.0.offxml")
    # add an atom smirks for boron
    boron = BespokeAtomSmirks(
        smirks="[#5:1]",
        parameterize={"epsilon"},
        atoms={(0,)},
        epsilon=0.04,
        rmin_half=3,
    )
    # add boron with the flag
    ff.add_smirks(
        smirks=[
            boron,
        ],
        parameterize=False,
    )
    with temp_directory():
        ff.force_field.to_file(filename="boron.offxml")

        boron_ff = ForceField("boron.offxml", allow_cosmetic_attributes=False)
        # now look for the parameter we added
        boron_param = boron_ff.get_parameter_handler("vdW").parameters["[#5:1]"]
        # now make sure it has the param flag
        param_dict = boron_param.__dict__
        assert param_dict["_cosmetic_attribs"] == []
        assert "_parameterize" not in param_dict


def test_label_molecule():
    """
    Test that labeling a molecule with the editor works.
    """

    ff = ForceFieldEditor(force_field_name="openff-1.0.0.offxml")
    ethane = Molecule.from_file(
        file_path=get_data_file_path(
            os.path.join("test", "molecules", "ethane.sdf"), "openff.bespokefit"
        ),
        file_format="sdf",
    )

    labels = ff.label_molecule(molecule=ethane)
    for param_type in ["Bonds", "Angles", "ProperTorsions", "ImproperTorsions", "vdW"]:
        assert param_type in labels


@pytest.mark.parametrize(
    "smirks_data",
    [
        pytest.param(
            (
                BespokeAtomSmirks(
                    smirks="[#1:1]", atoms={(0,)}, epsilon=0.01, rmin_half=3
                ),
                {
                    "epsilon": "0.0157 * mole**-1 * kilocalorie",
                    "rmin_half": "0.6 * angstrom",
                },
            ),
            id="Atom smirks",
        ),
        pytest.param(
            (
                BespokeBondSmirks(
                    smirks="[#6X4:1]-[#6X4:2]", atoms={(0, 1)}, k=100, length=2
                ),
                {
                    "length": "1.520375903275 * angstrom",
                    "k": "531.1373738609999 * angstrom**-2 * mole**-1 * kilocalorie",
                },
            ),
            id="Bond smirks",
        ),
        pytest.param(
            (
                BespokeAngleSmirks(
                    smirks="[*:1]~[#6X4:2]-[*:3]", atoms={(0, 1, 2)}, k=100, angle=120
                ),
                {
                    "angle": "107.6607821752 * degree",
                    "k": "101.7373362367 * mole**-1 * radian**-2 * kilocalorie",
                },
            ),
            id="Angle smirks",
        ),
        pytest.param(
            (
                BespokeTorsionSmirks(
                    smirks="[*:1]-[#6X4:2]-[#6X4:3]-[*:4]",
                    atoms={(0, 1, 2, 3)},
                    terms={"3": BespokeTorsionTerm(periodicity=3)},
                ),
                {
                    "k": "0.2042684902198 * mole**-1 * kilocalorie",
                    "phase": "0.0 * degree",
                },
            ),
            id="Torsion smirks",
        ),
    ],
)
def test_updating_smirks(smirks_data):
    """
    Test that each smirks type can be updated from a given force field file.
    """
    smirks, updated_params = smirks_data

    ff = ForceFieldEditor(force_field_name="openff-1.0.0.offxml")
    ff.update_smirks_parameters(
        smirks=[
            smirks,
        ]
    )

    if smirks.type.value != "ProperTorsions":
        for param, value in updated_params.items():
            assert getattr(smirks, param) == value

    else:
        term = smirks.terms["3"]
        for param, value in updated_params.items():
            assert getattr(term, param) == value
