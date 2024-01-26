import pytest

from openff.bespokefit._pydantic import ValidationError
from openff.bespokefit.schema.smirnoff import (
    AngleSMIRKS,
    BondSMIRKS,
    ImproperTorsionSMIRKS,
    ProperTorsionSMIRKS,
    VdWSMIRKS,
)


def test_vdw_check_smirks():
    # The passing case
    VdWSMIRKS(smirks="[#6:1]", attributes={"epsilon"})

    # The failing case.
    with pytest.raises(ValidationError):
        VdWSMIRKS(smirks="[#6:1]-[#6:2]", attributes={"epsilon"})


def test_bond_check_smirks():
    # The passing case
    BondSMIRKS(smirks="[#6:1]-[#6:2]", attributes={"k"})

    # The failing case.
    with pytest.raises(ValidationError):
        BondSMIRKS(smirks="[#6:1]-[#6:2]-[#6:3]", attributes={"k"})


def test_angle_check_smirks():
    # The passing case
    AngleSMIRKS(smirks="[#6:1]-[#6:2]-[#6:3]", attributes={"k"})

    # The failing case.
    with pytest.raises(ValidationError):
        AngleSMIRKS(smirks="[#6:1]-[#6:2]-[#6:3]-[#6:4]", attributes={"k"})


def test_proper_torsion_check_smirks():
    # The passing case
    ProperTorsionSMIRKS(smirks="[#6:1]-[#6:2]-[#6:3]-[#6:4]", attributes={"k1"})

    # The failing case.
    with pytest.raises(ValidationError):
        ProperTorsionSMIRKS(smirks="[#6:1]-[#6:2]-[#6:3]", attributes={"k"})


def test_improper_torsion_check_smirks():
    # The passing case
    ImproperTorsionSMIRKS(smirks="[#6:1]-[#6:2]-[#6:3]-[#6:4]", attributes={"k1"})

    # The failing case.
    with pytest.raises(ValidationError):
        ImproperTorsionSMIRKS(smirks="[#6:1]-[#6:2]-[#6:3]", attributes={"k"})
