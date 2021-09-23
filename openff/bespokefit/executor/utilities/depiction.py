import functools
from typing import Optional, Tuple

IMAGE_UNAVAILABLE_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" style="isolation:isolate" viewBox="0 0 200 200" width="200pt" height="200pt"><defs><clipPath id="_clipPath_eSdCSpw1sB1xWp7flmMoZ0WjTPwPpzQh"><rect width="200" height="200"/></clipPath></defs><g clip-path="url(#_clipPath_eSdCSpw1sB1xWp7flmMoZ0WjTPwPpzQh)"><g clip-path="url(#_clipPath_LvpdWbrYj1cREqoXz8Lwbk3ZilfC6tg9)"><text transform="matrix(1,0,0,1,44.039,91.211)" style="font-family:'Open Sans';font-weight:400;font-size:30px;font-style:normal;fill:#000000;stroke:none;">Preview</text><text transform="matrix(1,0,0,1,17.342,132.065)" style="font-family:'Open Sans';font-weight:400;font-size:30px;font-style:normal;fill:#000000;stroke:none;">Unavailable</text></g><defs><clipPath id="_clipPath_LvpdWbrYj1cREqoXz8Lwbk3ZilfC6tg9"><rect x="0" y="0" width="166" height="81.709" transform="matrix(1,0,0,1,17,59.146)"/></clipPath></defs></g></svg>
"""


def _oe_smiles_to_image(smiles: str, highlight_atoms: Tuple[int]) -> str:

    from openeye import oechem, oedepict

    image = oedepict.OEImage(200, 200)

    opts = oedepict.OE2DMolDisplayOptions(200, 200, oedepict.OEScale_AutoScale)
    opts.SetAromaticStyle(oedepict.OEAromaticStyle_Circle)
    opts.SetMargins(5)

    oe_molecule = oechem.OEGraphMol()
    oechem.OESmilesToMol(oe_molecule, smiles)

    highlighted_atoms = [
        atom
        for atom in oe_molecule.GetAtoms()
        if atom.GetMapIdx() > 0 and atom.GetMapIdx() in highlight_atoms
    ]

    for atom in oe_molecule.GetAtoms():
        atom.SetMapIdx(0)

    oedepict.OEPrepareDepiction(oe_molecule)

    display = oedepict.OE2DMolDisplay(oe_molecule, opts)

    highlighted_set = oechem.OEAtomBondSet()

    for atom in highlighted_atoms:
        highlighted_set.AddAtom(atom)

    oedepict.OEAddHighlighting(
        display,
        oechem.OEColor(oechem.OELimeGreen),
        oedepict.OEHighlightStyle_BallAndStick,
        highlighted_set,
    )

    oedepict.OERenderMolecule(image, display)

    svg_content = oedepict.OEWriteImageToString("svg", image)
    return svg_content.decode()


def _rd_smiles_to_image(smiles: str, highlight_atoms: Tuple[int]) -> str:

    from rdkit import Chem
    from rdkit.Chem.Draw import rdMolDraw2D

    smiles_parser = Chem.rdmolfiles.SmilesParserParams()
    smiles_parser.removeHs = True

    rdkit_molecule = Chem.MolFromSmiles(smiles, smiles_parser)

    highlight_atom_indices = [
        atom.GetIdx()
        for atom in rdkit_molecule.GetAtoms()
        if atom.GetAtomMapNum() in highlight_atoms
    ]

    for atom in rdkit_molecule.GetAtoms():
        atom.SetAtomMapNum(0)

    if not rdkit_molecule.GetNumConformers():
        Chem.rdDepictor.Compute2DCoords(rdkit_molecule)

    drawer = rdMolDraw2D.MolDraw2DSVG(200, 200, 150, 200)
    drawer.drawOptions().padding = 0.05

    drawer.SetOffset(25, 0)
    drawer.DrawMolecule(rdkit_molecule, highlightAtoms=highlight_atom_indices)

    drawer.FinishDrawing()

    svg_content = drawer.GetDrawingText()
    return svg_content


@functools.lru_cache(100000)
def smiles_to_image(smiles: str, highlight_atoms: Optional[Tuple[int]] = None):

    highlight_atoms = tuple() if highlight_atoms is None else highlight_atoms

    try:
        return _oe_smiles_to_image(smiles, highlight_atoms)
    except (ModuleNotFoundError, ImportError):
        return _rd_smiles_to_image(smiles, highlight_atoms)
