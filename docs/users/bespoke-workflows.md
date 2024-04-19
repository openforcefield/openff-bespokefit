(workflow_chapter)=
# Fitting workflows

The settings and steps by which a new bespoke force field is generated is referred to as a fitting workflow within 
bespoke fit (represented by the [`BespokeOptimizationSchema`] object), and are usually created by feeding an OpenFF 
[`Molecule`] object into a [`BespokeWorkflowFactory`].

[`BespokeOptimizationSchema`]: openff.bespokefit.schema.fitting.BespokeOptimizationSchema
[`BespokeWorkflowFactory`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory

[`Molecule`]: openff.toolkit.topology.Molecule

## The default workflow

The default workflow is suitable for augmenting a general [SMIRNOFF] force field (currently the [OpenFF 2.2.0] force
field) with a new bespoke torsion term for each non-terminal rotatable bond in the input molecule, trained to reproduce
a bespoke one-dimensional quantum chemical torsion scan performed around that bond.

[SMIRNOFF]: https://openforcefield.github.io/standards/standards/smirnoff/

In this section, we'll build this workflow factory up from nothing. This is just for a demonstration; you can
always build this factory by simply instantiating the `BespokeWorkflowFactory` class without arguments.

The default workflow has five steps:

1. **Parameter selection:** Choose the features of the molecule to create bespoke 
    parameters for.
2. **Fragmentation:** Break the molecule into parts large enough to have accurate
    chemistry, but small enough for efficient quantum chemical calculations.
3. **QC Generation:** Perform quantum chemical calculations on the fragments to
    generate reference data for the bespoke parameters to reproduce.
4. **Parameter generation:** Generate SMIRKS codes encoding the chosen molecular
    features and choose starting values for their parameters
5. **Optimization:** Optimize the force field parameters into bespoke parameters
    that reproduce the quantum chemical data.

A workflow factory can be constructed piecemeal by first calling the constructor to create one with the default settings,
and then overriding them by assigning to each field later:

```python
from openff.bespokefit.workflows import BespokeWorkflowFactory

factory = BespokeWorkflowFactory()
```

### Parameter selection

Torsion parameters are selected for bespoke fitting by specifying a list of SMIRKS patterns to the
[`target_torsion_smirks`] field. Each SMIRKS pattern should have two indexed atoms; torsion parameters
will be generated for rotations around the bond between these atoms:

```python
from openff.fragmenter.fragment import WBOFragmenter

factory.target_torsion_smirks = ['[!#1]~[!$(*#*)&!D1:1]-,=;!@[!$(*#*)&!D1:2]~[!#1]']
```

[`target_torsion_smirks`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.target_torsion_smirks

### Fragmentation

BespokeFit uses [OpenFF Fragmenter] to fragment molecules. Fragmentation can be configured by subclasses of the titular
[`Fragmenter`] class, which are accepted directly by BespokeFit. By default, the fragmentation scheme aims to ensure
the Wiberg bond order (WBO) of the target bond is the same in the parent and the fragment is used. This is used as a
proxy of the electronic environment around the bond. Fragmentation is configured via the [`fragmentation_engine`] field:

```python
from openff.fragmenter.fragment import WBOFragmenter

factory.fragmentation_engine = WBOFragmenter()
```

[`fragmentation_engine`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.fragmentation_engine

### QC Generation

BespokeFit uses target schemas to define the types of reference data to train the bespoke parameters to. Each target
type has a corresponding QC data type that must be generated as part of the bespoke fitting process to use as a 
reference. A target that measures the deviation between a QC and MM torsion scan, for example, will require a 1D QC 
torsion scan to be performed. 

The target schema also describes how strongly deviations from the reference data contributes to the overall loss 
function to be minimzed during the optimization stage. Target schema classes are subclasses of [`BaseTargetSchema`], 
and schemas for torsion drives, vibration fitting, and several other targets are available in the 
[`openff.bespokefit.schema.targets`] module. Target schemas are specified with the [`target_templates`] field:

```python
from openff.bespokefit.schema.targets import TorsionProfileTargetSchema

factory.target_templates = [TorsionProfileTargetSchema()]
```

We can also specify how we want to generate any reference data, including the program used, method, basis set, and 
level of theory. This is specified with instances of the [`QCSpec`] class from [QCSubmit]. If multiple specifications 
are provided, the factory will try them in order until it finds one that is both available on the executing machine and 
that supports the target molecule. Note that this may lead to BespokeFit silently behaving differently on machines with 
different software installed. Reference data generation methods are specified via the [`default_qc_specs`] field:

```python
from openff.qcsubmit.common_structures import QCSpec

factory.default_qc_specs = [QCSpec()]
```

[`target_templates`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.target_templates
[`BaseTargetSchema`]: openff.bespokefit.schema.targets.BaseTargetSchema
[`openff.bespokefit.schema.targets`]: openff.bespokefit.schema.targets
[`QCSpec`]: openff.qcsubmit.common_structures.QCSpec
[QCSubmit]: https://github.com/openforcefield/openff-qcsubmit
[`default_qc_specs`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.default_qc_specs

### Parameter generation

Generation of SMIRKS codes for the bespoke parameters can be configured through the [`smirk_settings`] field, which takes
a [`SMIRKSettings`] object:

```python
from openff.bespokefit.utilities.smirks import SMIRKSettings

factory.smirk_settings = SMIRKSettings(
    expand_torsion_terms=True,
    generate_bespoke_terms=True,
)
```

Parameter generation also needs an initial force field to use as a starting point. The [`initial_force_field`] field
should be the filename of a force field in [offxml format]:

```python
factory.initial_force_field = "openff-2.2.0.offxml"
```

[`smirk_settings`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.smirk_settings
[`SMIRKSettings`]: openff.bespokefit.utilities.smirks.SMIRKSettings
[`initial_force_field`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.initial_force_field

### Optimization

BespokeFit optimizers are configured by subclasses of [`BaseOptimizerSchema`]. The default workflow uses [ForceBalance] 
to optimize torsion parameters, so we'll use [`ForceBalanceSchema`] to configure it. The default settings are designed 
for optimizing parameters of an OpenFF force field, and can be configured via the [`optimizer`] field:

```python
from openff.bespokefit.schema.optimizers import ForceBalanceSchema

factory.optimizer = ForceBalanceSchema()
```

Finally, we need to configure hyperparameters that describe the parameter's priors and how they can be fitted to the
reference data. Hyperparameter classes inherit from [`BaseSMIRKSHyperparameters`]; specific classes for [bonds],
[angles], [proper] and [improper] torsions, and [van der Waals forces] are available. Since we're only fitting proper
torsions, only those hyperparameters are needed; they can be specified via the [`parameter_hyperparameters`] field:

```python
from openff.bespokefit.schema.smirnoff import  ProperTorsionHyperparameters

factory.parameter_hyperparameters = [ProperTorsionHyperparameters()]
```

[`BaseSMIRKSHyperparameters`]: openff.bespokefit.schema.smirnoff.BaseSMIRKSHyperparameters
[bonds]: openff.bespokefit.schema.smirnoff.BondHyperparameters
[angles]: openff.bespokefit.schema.smirnoff.AngleHyperparameters
[proper]: openff.bespokefit.schema.smirnoff.ProperTorsionHyperparameters
[improper]: openff.bespokefit.schema.smirnoff.ImproperTorsionHyperparameters
[van der Waals forces]: openff.bespokefit.schema.smirnoff.VdWHyperparameters
[OpenFF Fragmenter]: https://github.com/openforcefield/openff-fragmenter
[`Fragmenter`]: openff.fragmenter.fragment.Fragmenter
[ForceBalance]: https://github.com/leeping/forcebalance
[`ForceBalanceSchema`]: openff.bespokefit.schema.optimizers.ForceBalanceSchema
[OpenFF 2.2.0]: https://openforcefield.org/force-fields/force-fields/#sage
[`BaseOptimizerSchema`]: openff.bespokefit.schema.optimizers.BaseOptimizerSchema
[offxml format]: https://openforcefield.github.io/standards/standards/smirnoff/
[`optimizer`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.optimizer
[`parameter_hyperparameters`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.parameter_hyperparameters

## Constructing a workflow

Once the workflow factory has been configured, a workflow for a particular molecule can be constructed with the 
[`optimization_schema_from_molecule()`] method:

```python
from openff.toolkit import Molecule

biphenyl = Molecule.from_smiles("C1=CC=C(C=C1)C2=CC=CC=C2")
workflow = factory.optimization_schema_from_molecule(biphenyl)
```

[`optimization_schema_from_molecule()`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.optimization_schema_from_molecule

## Sharing a workflow factory

It's very important to be able to share a customized workflow factory, both so that any results produced can be
reproducibly documented in the scientific literature and so that we can be sure we're using the same procedure on
different molecules at different times. Workflow factories can be saved to disk with the [`to_file()`] method:

```python
factory.to_file("my_bespoke_workflow.json")
```

The resulting JSON file can be distributed with a paper or pre-print, or shared with colleagues. Exported factories can
then be used either with the[`BespokeWorkflowFactory.from_file()`] class method:

```python
from openff.bespokefit.workflows import BespokeWorkflowFactory
factory = BespokeWorkflowFactory.from_file("my_bespoke_workflow.json")
```

[`to_file()`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.to_file
[`BespokeWorkflowFactory.from_file()`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.from_file
