"""
Test the smirks schema objects.
"""

import pytest
from chemper.graphs.environment import SMIRKSParsingError
from openff.toolkit.typing.engines.smirnoff import (
    AngleHandler,
    BondHandler,
    ForceField,
    ProperTorsionHandler,
    vdWHandler,
)
from pydantic import ValidationError

from openff.bespokefit.schema.bespoke.smirks import (
    BespokeAngleSmirks,
    BespokeAtomSmirks,
    BespokeBondSmirks,
    BespokeTorsionSmirks,
    BespokeTorsionTerm,
)
from openff.bespokefit.utilities.smirks import compare_smirks_graphs


@pytest.mark.parametrize(
    "smirks_data",
    [
        pytest.param(("[#1:1]", None), id="Valid atom smirks"),
        pytest.param(("[#1]", SMIRKSParsingError), id="Missing tag"),
        pytest.param(("[#1:1]-[#6:2]", ValidationError), id="Two tags error"),
        pytest.param(
            ("[CH3:7][CH3:8]>>[CH3:7][CH3:8]", SMIRKSParsingError),
            id="Reaction smarts error",
        ),
        pytest.param(("C.C", SMIRKSParsingError), id="Molecle complex"),
    ],
)
def test_atom_smirks(smirks_data):
    """
    Test validating the number of tagged atoms in a atom smirks.
    """
    smirks_pattern, error = smirks_data
    if error is None:
        smirks = BespokeAtomSmirks(
            smirks=smirks_pattern, atoms={(0,)}, epsilon=0.1, rmin_half=3
        )
        assert smirks.smirks == smirks_pattern
    else:
        with pytest.raises(error):
            _ = BespokeAtomSmirks(
                smirks=smirks_pattern, atoms={(0,)}, epsilon=0.1, rmin_half=3
            )


@pytest.mark.parametrize(
    "smirks_data",
    [
        pytest.param(("[#1:1]-[#6:2]", None), id="Valid bond smirks"),
        pytest.param(("[#1]", SMIRKSParsingError), id="Missing all tags"),
        pytest.param(("[#1:1]-[#6:2]=[#6:3]", ValidationError), id="Three tags error"),
    ],
)
def test_bond_smirks(smirks_data):
    """
    Test validating the number of tagged atoms in a bond smirks.
    """
    smirks_pattern, error = smirks_data
    if error is None:
        smirks = BespokeBondSmirks(
            smirks=smirks_pattern, atoms={(0, 1)}, k=500, length=2
        )
        assert smirks.smirks == smirks_pattern
    else:
        with pytest.raises(error):
            _ = BespokeBondSmirks(
                smirks=smirks_pattern, atoms={(0, 1)}, k=500, length=2
            )


@pytest.mark.parametrize(
    "smirks_data",
    [
        pytest.param(("[#1:1]-[#6:2]-[#6:3]", None), id="Valid angle smirks"),
        pytest.param(("[#1]", SMIRKSParsingError), id="Missing all tags"),
        pytest.param(("[#1:1]-[#6:2]", ValidationError), id="Two tags error"),
    ],
)
def test_angle_smirks(smirks_data):
    """
    Test validating the number of tagged atoms in a bond smirks.
    """
    smirks_pattern, error = smirks_data
    if error is None:
        smirks = BespokeAngleSmirks(
            smirks=smirks_pattern, atoms={(0, 1, 2)}, k=500, angle=120
        )
        assert smirks.smirks == smirks_pattern
    else:
        with pytest.raises(error):
            _ = BespokeAngleSmirks(
                smirks=smirks_pattern, atoms={(0, 1, 2)}, k=500, angle=120
            )


@pytest.mark.parametrize(
    "smirks_data",
    [
        pytest.param(("[#1:1]-[#6:2]-[#6:3]-[#1:4]", None), id="Valid torsion smirks"),
        pytest.param(("[#1]", SMIRKSParsingError), id="Missing all tags"),
        pytest.param(("[#1:1]-[#6:2]", ValidationError), id="Two tags error"),
    ],
)
def test_torsion_smirks(smirks_data):
    """
    Test validating the number of tagged atoms in a bond smirks.
    """
    smirks_pattern, error = smirks_data
    if error is None:
        smirks = BespokeTorsionSmirks(smirks=smirks_pattern, atoms={(0, 1, 2, 3)})
        assert smirks.smirks == smirks_pattern
    else:
        with pytest.raises(error):
            _ = BespokeTorsionSmirks(smirks=smirks_pattern, atoms={(0, 1, 2, 3)})


def test_atom_units():
    """
    Make sure that atom smirk units are applied.
    """

    smirk = BespokeAtomSmirks(smirks="[#1:1]", atoms={(0,)}, epsilon=0.1, rmin_half=2)
    assert smirk.epsilon == "0.1 * mole**-1 * kilocalorie"
    assert smirk.rmin_half == "2 * angstrom"


def test_bond_units():
    """
    Make sure that bond units are applied.
    """
    smirk = BespokeBondSmirks(smirks="[#1:1]-[#6:2]", atoms={(0, 1)}, k=500, length=2)
    assert smirk.k == "500 * angstrom**-2 * mole**-1 * kilocalorie"
    assert smirk.length == "2 * angstrom"


def test_angle_units():
    """
    Make sure that angle units are applied.
    """
    smirk = BespokeAngleSmirks(
        smirks="[#1:1]-[#6:2]-[#6:3]", atoms={(0, 1, 2)}, k=100, angle=120
    )
    assert smirk.k == "100 * mole**-1 * radian**-2 * kilocalorie"
    assert smirk.angle == "120 * degree"


def test_torsion_units():
    """
    Make sure that torsion units are applied.
    """
    smirk = BespokeTorsionTerm(periodicity=1, phase=27, k=10)
    assert smirk.phase == "27 * degree"
    assert smirk.k == "10 * mole**-1 * kilocalorie"


def test_general_parameterize():
    """
    Make sure that only attributes of this class can have a parameterize flag.
    """

    smirk = BespokeAngleSmirks(
        smirks="[#1:1]-[#6:2]-[#6:3]", atoms={(0, 1, 2)}, k=100, angle=120
    )
    smirk.parameterize = {"k"}
    # try and set a value not allowed
    with pytest.raises(ValueError):
        smirk.parameterize = {"length"}


def test_torsion_parameterize():
    """
    Make sure that only k values are accepted.
    """
    smirk = BespokeTorsionSmirks(
        smirks="[#1:1]-[#6:2]-[#6:3]-[#1:4]", atoms={(0, 1, 2, 3)}
    )
    smirk.parameterize = {"k1", "k2"}
    with pytest.raises(ValueError):
        smirk.parameterize = {"angle", "phase"}


def test_torsion_term():
    """
    Make sure the periodicity is validated for the torsion terms.
    """
    term = BespokeTorsionTerm(periodicity=1, phase=0)
    # try and change to a not supported value
    with pytest.raises(ValueError):
        term.periodicity = 7


def test_adding_torsion_term():
    """
    Test adding torsion terms.
    """

    torsion = BespokeTorsionSmirks(
        smirks="[#1:1]-[#6:2]-[#6:3]-[#1:4]", atoms={(0, 1, 2, 3)}
    )
    torsion.add_torsion_term(term="k2")
    assert "2" in torsion.terms
    # now add a term with invalid p
    with pytest.raises(ValidationError):
        torsion.add_torsion_term(term="k7")


@pytest.mark.parametrize(
    "smirks_data",
    [
        pytest.param(
            (
                BespokeAtomSmirks(
                    smirks="[#1:1]", atoms={(0,)}, epsilon=0.1, rmin_half=2
                ),
                vdWHandler.vdWType,
            ),
            id="Atom smirks",
        ),
        pytest.param(
            (
                BespokeBondSmirks(
                    smirks="[#1:1]-[#6:2]", atoms={(0, 1)}, k=500, length=2
                ),
                BondHandler.BondType,
            ),
            id="Bond smirks",
        ),
        pytest.param(
            (
                BespokeAngleSmirks(
                    smirks="[#1:1]-[#6:2]-[#6:3]", atoms={(0, 1, 2)}, k=100, angle=120
                ),
                AngleHandler.AngleType,
            ),
            id="Angle smirks",
        ),
        pytest.param(
            (
                BespokeTorsionSmirks(
                    smirks="[#1:1]-[#6:2]-[#6:3]-[#1:4]",
                    atoms={(0, 1, 2, 3)},
                    terms={"1": BespokeTorsionTerm(periodicity=1)},
                ),
                ProperTorsionHandler.ProperTorsionType,
            ),
            id="Torsion smirks",
        ),
    ],
)
def test_atom_smirks_to_off(smirks_data):
    """
    Make sure the smirks schema can be converted to off_smirks type.
    """
    smirk_schema, off_type = smirks_data
    off = off_type(**smirk_schema.to_off_smirks())
    assert off.smirks == smirk_schema.smirks


@pytest.mark.parametrize(
    "smirks",
    [
        pytest.param(
            (
                BespokeAtomSmirks(
                    smirks="[#1:1]", atoms={(0,)}, epsilon=0.1, rmin_half=2
                ),
                BespokeAtomSmirks(
                    smirks="[#1:1]", atoms={(0,)}, epsilon=0.1, rmin_half=2
                ),
                True,
            ),
            id="Same smirks",
        ),
        pytest.param(
            (
                BespokeAtomSmirks(
                    smirks="[#1:1]", atoms={(0,)}, epsilon=0.1, rmin_half=2
                ),
                BespokeBondSmirks(
                    smirks="[#1:1]-[#6:2]", atoms={(0, 1)}, k=500, length=2
                ),
                False,
            ),
            id="Different types",
        ),
    ],
)
def test_smirks_equal_types(smirks):
    """
    Test that the smirks comparison type checks work.
    """
    smirks1, smirks2, result = smirks
    if result:
        assert smirks1 == smirks2
    else:
        assert smirks1 != smirks2


@pytest.mark.parametrize(
    "smirks",
    [
        pytest.param(
            ("[#6X4]-[#1:1]", "[#1:1]-[#6X4]", True), id="Same atom smirks reversed"
        ),
        pytest.param(("[#1:1]", "[#1:1]-[#6X4]", False), id="Different atom smirks"),
        pytest.param(("[#1:1]-[#6X4]", "[#1:1]-[#6X4]", True), id="Same atom smirks"),
        pytest.param(("[#6X4:1]-[#6X4:2]", "[#6X4:1]-[#6X4:2]", True), id="Same bond"),
        pytest.param(
            ("[#6X4:2]-[#6X4:1]", "[#6X4:1]-[#6X4:2]", True),
            id="Same bond reversed index",
        ),
        pytest.param(
            ("[#6X3:1]-[#6X4:2]", "[#6X4:2]-[#6X3:1]", True),
            id="Same bond reversed terms",
        ),
        pytest.param(
            ("[#6X4:3]-[#6X4:5]", "[#6X4:1]-[#6X4:2]", False),
            id="Same bond wrong index",
        ),
        pytest.param(
            ("[#6X3:1](~[#8X1])~[#8X1:2]", "[#6X3:2](~[#8X1])~[#8X1:1]", True),
            id="Same bond extras",
        ),
        pytest.param(
            ("[#6X4:1]-[#6X3:2]", "[#6X4:1]-[#6X3:2]=[#8X1+0]", False),
            id="Different bond",
        ),
        pytest.param(
            ("[*:3]~[#6X4:2]-[*:1]", "[*:1]~[#6X4:2]-[*:3]", True),
            id="Same angle reversed",
        ),
        pytest.param(
            ("[*:6]~[#6X4:2]-[*:1]", "[*:1]~[#6X4:2]-[*:3]", False),
            id="Same angle wrong index",
        ),
        pytest.param(
            ("[*:4]-[#6X4:3]-[#6X4:2]-[*:1]", "[*:1]-[#6X4:2]-[#6X4:3]-[*:4]", True),
            id="Same torsion reversed index",
        ),
        pytest.param(
            ("[*:1]-[#6X3:2]-[#6X4:3]-[*:4]", "[*:4]-[#6X4:3]-[#6X3:2]-[*:1]", True),
            id="Same torsion reversed terms",
        ),
        pytest.param(
            (
                "[#16X2,#16X1-1,#16X3+1:1]-[#6X3:2]-[#6X4:3]-[#7X3$(*-[#6X3,#6X2]):4]",
                "[*:1]-[#6X4:2]-[#6X4:3]-[*:4]",
                False,
            ),
            id="Different torsion",
        ),
        pytest.param(
            ("[#6X4]-[#1:1]", "[#6X4:1]-[#1:2]", False), id="Different no of index"
        ),
    ],
)
def test_smirks_equal(smirks):
    """
    Make sure smirks graph checks work correctly.
    """
    smirks1, smirks2, result = smirks
    assert compare_smirks_graphs(smirks1, smirks2) is result


@pytest.mark.parametrize(
    "smirks_data",
    [
        pytest.param(
            (
                BespokeAtomSmirks(
                    smirks="[#53X0-1:1]", atoms={(0,)}, epsilon=0, rmin_half=0
                ),
                {
                    "epsilon": 0.0536816,
                    "rmin_half": 2.86,
                },
            ),
            id="Update atom smirks",
        ),
        pytest.param(
            (
                BespokeBondSmirks(
                    smirks="[#6X4:1]-[#6X4:2]", atoms={(0, 1)}, length=0, k=0
                ),
                {
                    "k": 531.137373861,
                    "length": 1.520375903275,
                },
            ),
            id="Update bond smirks",
        ),
        pytest.param(
            (
                BespokeAngleSmirks(
                    smirks="[*:1]~[#6X4:2]-[*:3]", atoms={(0, 1, 2)}, angle=0, k=0
                ),
                {
                    "angle": 107.6607821752,
                    "k": 101.7373362367,
                },
            ),
            id="Update angle smirks",
        ),
        pytest.param(
            (
                BespokeTorsionSmirks(
                    smirks="[*:1]-[#6X4:2]-[#6X4:3]-[*:4]",
                    atoms={(0, 1, 2, 3)},
                    terms={"1": BespokeTorsionTerm(periodicity=1)},
                ),
                {
                    "periodicity": 3,
                    "phase": 0.0,
                    "k": 0.2042684902198,
                    "idivf": 1,
                },
            ),
            id="Update torsion smirks",
        ),
    ],
)
def test_update_parameters(smirks_data):
    """
    Test updating the smirks parameters using openff types.
    """
    smirk, result = smirks_data
    # load a forcefield
    ff = ForceField("openff-1.0.0.offxml")
    # all input smirks have parameters set to 0
    off_parameter = ff.get_parameter_handler(smirk.type).parameters[smirk.smirks]
    smirk.update_parameters(off_smirk=off_parameter)

    if smirk.type.value != "ProperTorsions":
        for param, value in result.items():
            assert float(getattr(smirk, param).split()[0]) == pytest.approx(value)

    else:
        term = smirk.terms["3"]
        for param, value in result.items():
            assert float(getattr(term, param).split()[0]) == pytest.approx(value)
