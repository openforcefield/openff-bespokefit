import pytest
from pydantic import ValidationError

from openff.bespokefit.schema.smirks import (
    AngleSmirks,
    BondSmirks,
    ImproperTorsionSmirks,
    ProperTorsionSmirks,
    VdWSmirks,
)


def test_vdw_check_smirks():

    # The passing case
    VdWSmirks(smirks="[#6:1]", attributes={"epsilon"})

    # The failing case.
    with pytest.raises(ValidationError):
        VdWSmirks(smirks="[#6:1]-[#6:2]", attributes={"epsilon"})


def test_bond_check_smirks():

    # The passing case
    BondSmirks(smirks="[#6:1]-[#6:2]", attributes={"k"})

    # The failing case.
    with pytest.raises(ValidationError):
        BondSmirks(smirks="[#6:1]-[#6:2]-[#6:3]", attributes={"k"})


def test_angle_check_smirks():

    # The passing case
    AngleSmirks(smirks="[#6:1]-[#6:2]-[#6:3]", attributes={"k"})

    # The failing case.
    with pytest.raises(ValidationError):
        AngleSmirks(smirks="[#6:1]-[#6:2]-[#6:3]-[#6:4]", attributes={"k"})


def test_proper_torsion_check_smirks():

    # The passing case
    ProperTorsionSmirks(smirks="[#6:1]-[#6:2]-[#6:3]-[#6:4]", attributes={"k1"})

    # The failing case.
    with pytest.raises(ValidationError):
        ProperTorsionSmirks(smirks="[#6:1]-[#6:2]-[#6:3]", attributes={"k"})


def test_improper_torsion_check_smirks():

    # The passing case
    ImproperTorsionSmirks(smirks="[#6:1]-[#6:2]-[#6:3]-[#6:4]", attributes={"k1"})

    # The failing case.
    with pytest.raises(ValidationError):
        ImproperTorsionSmirks(smirks="[#6:1]-[#6:2]-[#6:3]", attributes={"k"})
