import pytest

from openff.bespokefit.executor.utilities.depiction import (
    _oe_smiles_to_image,
    _rd_smiles_to_image,
    smiles_to_image,
)


@pytest.mark.parametrize(
    "to_image", [_oe_smiles_to_image, _rd_smiles_to_image, smiles_to_image]
)
def test_smiles_to_image(to_image):
    try:
        svg_contents = to_image("C", tuple())

    except ModuleNotFoundError as e:
        pytest.skip(f"missing optional dependency - {e.name}")
        return

    assert len(svg_contents) > 0 and "svg" in svg_contents
