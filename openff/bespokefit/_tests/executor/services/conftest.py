import hashlib

import pytest
from openff.fragmenter.fragment import Fragment, FragmentationResult

from openff.bespokefit.schema.fitting import (
    BespokeOptimizationSchema,
    OptimizationStageSchema,
)
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.smirnoff import (
    BondHyperparameters,
    ProperTorsionHyperparameters,
)
from openff.bespokefit.utilities.smirnoff import ForceFieldEditor


@pytest.fixture()
def ptp1b_smiles() -> str:
    return (
        "[H:30][c:1]1[c:2]([c:6]([c:11]([c:7]([c:3]1[H:32])[H:36])[C:17](=[O:24])[N:21]([H:41])[c:12]2[c:8]([c:4]"
        "([c:5]([c:10]([c:9]2[H:38])[C:13]3=[C:15]([C:14](=[C:16]([S:28]3)[C:18](=[O:25])[O-:22])[O:27][C:20]([H:39])"
        "([H:40])[C:19](=[O:26])[O-:23])[Br:29])[H:34])[H:33])[H:37])[H:35])[H:31]"
    )


@pytest.fixture()
def ptp1b_fragment(ptp1b_smiles) -> FragmentationResult:
    """
    Mock the result of fragmentation of a ptp1b molecule.
    """
    return FragmentationResult(
        parent_smiles=ptp1b_smiles,
        fragments=[
            Fragment(
                smiles="[H:37][c:8]1[c:4]([c:5]([c:10]([c:9]([c:12]1[H])[H:38])[C:13]2=[C:15]([C:14]"
                "(=[C:16]([S:28]2)[H])[O:27][C:20]([H:39])([H:40])[H])[Br:29])[H:34])[H:33]",
                bond_indices=(10, 13),
            ),
        ],
        provenance={"test": 1.0},
    )


@pytest.fixture()
def ptp1b_input_schema_single(ptp1b_smiles) -> BespokeOptimizationSchema:
    """
    Mock an input schema for SMARTS generation testing.
    """

    force_field = ForceFieldEditor("openff_unconstrained-1.3.0.offxml")
    ff_hash = hashlib.sha512(force_field.force_field.to_string().encode()).hexdigest()
    return BespokeOptimizationSchema(
        id="ptp1b",
        initial_force_field=force_field.force_field.to_string(),
        initial_force_field_hash=ff_hash,
        stages=[
            OptimizationStageSchema(
                optimizer=ForceBalanceSchema(),
                parameters=[],
                parameter_hyperparameters=[ProperTorsionHyperparameters()],
                targets=[],
            )
        ],
        smiles="[H:30][c:1]1[c:2]([c:6]([c:11]([c:7]([c:3]1[H:32])[H:36])[C:17](=[O:24])[N:21]([H:41])[c:12]2[c:8]"
        "([c:4]([c:5]([c:10]([c:9]2[H:38])[C:13]3=[C:15]([C:14](=[C:16]([S:28]3)[C:18](=[O:25])[O-:22])[O:27]"
        "[C:20]([H:39])([H:40])[C:19](=[O:26])[O-:23])[Br:29])[H:34])[H:33])[H:37])[H:35])[H:31]",
        target_torsion_smirks=["[!#1]~[!$(*#*)&!D1:1]-,=;!@[!$(*#*)&!D1:2]~[!#1]"],
    )


@pytest.fixture()
def ptp1b_input_schema_multiple(ptp1b_input_schema_single) -> BespokeOptimizationSchema:
    """
    Mock a multi stage optimisation schema.
    """
    input_schema = ptp1b_input_schema_single.copy(deep=True)
    input_schema.stages.append(
        OptimizationStageSchema(
            optimizer=ForceBalanceSchema(),
            parameters=[],
            parameter_hyperparameters=[BondHyperparameters()],
            targets=[],
        )
    )
    return input_schema
