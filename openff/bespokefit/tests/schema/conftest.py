import pytest
from openff.qcsubmit.common_structures import MoleculeAttributes
from openff.toolkit.topology import Molecule
from simtk import unit

from openff.bespokefit.schema.bespoke.tasks import TorsionTask
from openff.bespokefit.schema.data import BespokeQCData


@pytest.fixture()
def ethane_torsion_task():

    molecule: Molecule = Molecule.from_mapped_smiles(
        "[H:9][O:3][C:1]([H:5])([H:6])[C:2]([H:7])([H:8])[O:4][H:10]"
    )
    molecule.generate_conformers(n_conformers=1)

    entry = TorsionTask(
        name="occo",
        fragment=False,
        input_conformers=[molecule.conformers[0].value_in_unit(unit.angstrom)],
        attributes=MoleculeAttributes.from_openff_molecule(molecule),
        dihedrals=[(2, 0, 1, 3)],
    )

    return entry


@pytest.fixture()
def ethane_bespoke_data(ethane_torsion_task):
    return BespokeQCData(tasks=[ethane_torsion_task])
