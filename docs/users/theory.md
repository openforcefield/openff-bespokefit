(bespoke_theory_chapter)=
# Theory

BespokeFit aims to produce highly accurate, "bespoke" classical molecular force field parameters for user-specified 
molecules, or even series of molecules that share common features such is common in lead series. In the page we will 
describe the theory behind the workflow used to produce such parameters, as well as any assumptions and trade-offs made.

The process by which bespoke parameters are generated generally follows five main stages:

1. **Parameter selection** - important features of the molecule(s) that require bespoke parameters, such as rotatable 
   bonds, are identified
2. **Fragmentation** - molecules are split into smaller fragments based on the identified features for faster quantum 
   chemical calculations
3. **QC generation** - any required quantum chemical reference data is generated using the smaller chemical fragments 
4. **Parameter generation** - bespoke SMIRKS patterns that match the identified chemical features are constructed and 
   initial values sourced from a general force field
5. **Parameter optimization** - the bespoke parameters are trained to the reference QC data

## Parameter selection

The first stage in the bespoke fitting workflow is identifying those features of a molecule that require parameters with 
high specificity in order to achieve the best accuracy. 

At present, this involves identifying all non-terminal rotatable bonds in a molecule. Accurately reproducing the torsion profile 
around such bonds is critical to ensuring that the correct conformational preferences of a molecule are captured.

:::{figure-md} fig-bonds
![2,6-dichloro-~{N}-[2-(2-ethylbutanoylamino)-4-pyridyl]benzamide with selected bonds highlighted](img/theory/rotatable_nonterminal_bonds.svg)

A hypothetical TYK2 ligand, highlighting each rotatable bond as identified by the default BespokeFit workflow.
:::

By default, we define a 'rotatable bond' as any bond that is not in a ring, and is between two 'non-terminal', not 
triple-bonded atoms. Any atoms that are bonded to at least two other non-hydrogen atoms are considered to be non-terminal. 
See the [bespoke workflow factory chapter](workflow_chapter) for details on overriding this definition of a 'rotatable 
bond'.

## Fragmentation

The second stage in the bespoke fitting workflow is fragmenting the larger molecule of interest into smaller fragments.

Quantum chemical calculations are usually very computationally expensive, and their expense grows very quickly with 
the number of atoms --- much more quickly than in molecular mechanics. A QC calculation with twice as many atoms 
generally takes much more than twice as long to complete. Like launching rockets in stages for fuel economy, the default
fitting workflow breaks large molecules into fragments for computational economy. 

These fragments are designed to be as small as possible without significantly changing the important features of the 
molecule identified in the first stage. To ensure the torsional profile of a rotatable bond is preserved, for example, 
fragments are generated in such a way as to preserve the electronic environment around that bond. 

:::{figure-md} fig-fragments
![Fragments generated from 2,6-dichloro-~{N}-[2-[[(2~{S})-2-ethyl-4-oxo-butanoyl]amino]-4-pyridyl]benzamide](img/theory/fragments.svg)

Fragments generated from the above TYK2 ligand. The bond around which each fragment is built is highlighted and the 
original molecule is in light gray. Note that some fragments are repeated because they share an electronically decoupled 
region of the molecule.
:::

The default fitting workflow employs the Wiberg Bond Order{cite}`wbofrag` fragmentation engine made available by 
the [`openff-fragmenter`] package [although this can be overidden](workflow_chapter). At present only torsion drives 
take advantage of fragmentation, and one fragment will be generated for each rotatable bond identified by the previous 
step.

[`openff-fragmenter`]: https://fragmenter.readthedocs.io/en/stable/index.html

## QC Generation

The third stage in the bespoke fitting workflow is generating any reference quantum chemical data that the bespoke 
parameters will be trained to reproduce.

The default fitting workflow currently generates all reference data at the *B3LYP-D3BJ/DZVP* level of theory. This was
chosen due to its balance of computational efficient and accuracy at reproducing conformations generated using higher 
levels of theories. This is also the level of theory used in training the main OpenFF force fields, and so ensures 
maximal compatability between the two when mixing bespoke and general parameters. 

:::{tip}
See the [quick start guide](quick_start_chapter) for details on how to swap out the default level of theory for 
a faster surrogate, such as ANI or XTB.
:::

The types of quantum calculation that will be performed depend on which types of bespoke parameters are being generated.
In particular if generating bespoke:

* **torsion parameters**: a one dimensional torsion scan around each identified bond will be performed

<!-- add paragraph / subsection on torsion drives generated using torsiondrive package using wavefront propagation + 
nice figure? -->

<!-- 
- For high throughput bespoke parameter deviation we recommend using the fantastic QCFracal distributed computing and database for quantum chemistry.
- Users can easily set up a local server and submit large datasets of torsiondrives using QCSubmit which can then be used as reference data by bespokefit via the cache update feature- need a section on how to pull down qcarchive data and cache locally. -->

## Parameter generation

The fourth and penultimate stage in the bespoke fitting workflow is to generate an initial set of bespoke parameters 
for each of the features identified in the first stage ready to train.

There are two aspects to this: we need to both select a sensible set of initial values for the parameter, and we need to 
generate a SMIRKS parameter that describes the chemical environment that the parameter will be applied to. 

:::{note}
[SMIRKS].{cite}`smirks` patterns are used extensively within OpenFF force fields as a more flexible and robust alternative to atom types.

<!-- add reference to original SMIRNOFF publication -->
:::

### Selecting initial values

The initial values for the bespoke parameters are by default sourced from the OpenFF 2.0.0 force field. This is done by
applying a general force field to the molecule of interest, inspecting which parameters from the general force field 
were applied to the aspects of the molecule that bespoke parameters are being generated for, and then copying the values 
associated with that general parameter. As an example, in the case of training bespoke torsion parameters for biphenyl, 
we would want to see which general torsion parameters were assigned to the central rotatable bond, and then copy the 
barrier height, phase and periodicity of those parameters over to the bespoke parameter.

Further than simply copying the values from the general force field, by default extra degrees of freedom will also be 
added. In the case of generating bespoke torsion parameters, the default fitting workflow will augment the initial 
values so that it contains periodicities $n_i$ from 1 to 4.

$$U(\phi) = \sum_{i=1}^N k_i (1 + \cos(n_i \phi - \psi_i))$$

This can be configured in the [`smirk_settings`] field of the workflow factory. This is a conservative approach that is 
often not needed; in these cases, added complexity is avoided because the barrier heights $k_i$ are kept close to zero 
by the optimizer, which prefers solutions with simpler parameters.

[`smirk_settings`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.smirk_settings

### Generating bespoke SMIRKS

When generating a SMIRKS pattern a trade-off must be made. Ideally the pattern would be highly specific to the 
chemical environment in question while being transferable to other similar chemical environments, such as the same 
torsion of a pharmacophore across several molecule in a lead series. While general force fields favor generality, 
BespokeFit prefers specificity so that parameters can be highly optimized to the target. SMIRKS patterns generated by 
BespokeFit are constructed to include as much information about as many atoms as possible while being consistent across 
the parent molecule and any relevant fragments.

:::{figure-md} fig-smirks
![SMIRKS pattern, fragment, and parent molecule. Indexed torsion atoms and atoms that are different in the fragment and parent are color-coded in both the pattern and the molecular structures.](img/theory/smirks.svg)

TYK2 ligand series binding fragment, alongside the parent molecule and the SMIRKS pattern for a torsion parameter. 
The torsion parameter is labeled with a rotation arrow. The four atoms that define the torsion parameter are highlighted 
in orange boldface. The `:1` -- `:4` suffixes in the SMIRKS patterns for these four atoms index them as defining the 
torsion, while the remainder of the pattern identifies the chemistry. The atoms that vary between the fragment and 
parent molecule are highlighted in blue and green; they are defined in the SMIRKS as a comma-separated list of possible 
chemistries. The chemistry used by the parent molecule is italicized.
:::

#### Torsion SMIRKS

Torsion SMIRKS generation begins by grouping symmetric torsions and treating them together. By symmetry, these torsions 
should have identical parameters, and this helps reduce the number of new parameters and simplify optimization. 
BespokeFit accomplishes this by identifying the symmetry classes of atoms in the parent molecule with RDKit or OpenEye 
and labeling torsions with the symmetry classes of their atoms. Two atoms will have the same symmetry class if and only 
if they are symmetry-equivalent, so symmetric torsions are those that share a (possibly reversed) label.

:::{figure-md} fig-symmetry
![First fragment of 2,6-dichloro-~{N}-[2-(2-ethylbutanoylamino)-4-pyridyl]benzamide with symmetry classes and symmetry-equivalent torsions labelled.](img/theory/symmetry_classes.svg)

The first fragment of the ligand, labelled with symmetry classes. Atoms with the same symmetry class are 
symmetry-equivalent. Below, two symmetry-equivalent torsions for the fragment are highlighted.
:::

Once a minimal set of symmetry-equivalent torsions are collected, SMIRKS patterns are generated with [ChemPer]. We 
consider the fragments to be the minimum electronically decoupled substructure around each torsion which preserves the 
local chemical environment. Hence, SMIRKS patterns are constructed to include the maximum common substructure between 
the parent and fragment giving them an ideal mix of specificity and transferability between parent and fragment and to other 
molecules that share the computed fragment. 

As a result, the common cores of congeneric series like the ligands of TYK2 (pictured) can be 
parameterized once and cached. When a new molecule produces the same torsion SMIRKS, the parameter can be reused from 
the cache, saving the significant computational effort associated with a torsion drive.

:::{figure-md} fig-variants
![9 TYK2 ligands with a common motif highlighted](img/theory/tyk2_shared_core.svg)

9 TYK2 ligands that share the binding fragment above. The highlighted fragment matches the SMIRKS code from 
[above](fig-smirks), which allows the torsion to be cached and reused.
:::

[ChemPer]: https://chemper.readthedocs.io/en/latest/

## Optimization

The final stage in the bespoke fitting workflow is to optimize ( / train) the bespoke parameters against the QC
reference data generating in the earlier stage.

The optimization proceeds by first constructing a loss function to minimize. In BespokeFit, we refer to the different
contributions to the loss function as *'fitting targets'* consistently with the brilliant [ForceBalance] force field
optimization framework.

Currently, BespokeFit mainly supports three main fitting targets which measures the deviations of:

* **torsion profile**: the torsion profile computed by performing a torsion scan using the 
  current force field parameters with the reference QC torsion profile.
* **vibrational frequency**: vibrational frequencies computed from MM hessian data to those computed from reference 
  QC hessian calculations.
* **optimized geometry**: internal coordinates of a conformer of the molecule minimized using the current values of the 
  force field to the conformer same minimized using QC methods. 

These are the exact same fitting targets that are used in producing the mainline OpenFF force fields, ensuring 
that any bespoke parameters yielded by the bespoke workflow are compatible with those in the starting general force 
field. For more details, see the [OpenFF 1.0.0 Parsley paper].{cite}`parsley`

Although in the future multiple optimization engines will be supported, by default the fitting workflow will employ 
[ForceBalance] to train the parameters against the fitting targets outlined above. 

ForceBalance employs a Bayesian prior distribution to avoid over-fitting and to define the range of likely values the 
fitted parameter may take on.{cite}`forcebalance` Any complexity added to the force field must overcome a penalty 
imposed by the prior distribution. The Laplacian prior used by default is equivalent to an L1 regulariser, and is 
configured by setting a "prior width", which sets the range over which the parameter can vary during optimization. 
BespokeFit defaults to quite large priors on the torsion barrier heights ($k$) so that the optimization is not hindered 
by a very general reference value.

[OpenFF 1.0.0 Parsley paper]: https://doi.org/10.1021/acs.jctc.1c00571
[ForceBalance]: http://leeping.github.io/forcebalance/doc/html/index.html
[SMIRKS]: https://doi.org/10.1021/acs.jctc.8b00640

## References

:::{bibliography}
:::