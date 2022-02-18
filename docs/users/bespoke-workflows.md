(workflow_chapter)=
# Fitting workflows

The settings and steps by which a new bespoke force field is generated is referred to as a fitting workflow within 
bespoke fit (represented by the [`BespokeOptimizationSchema`] object), and are usually created by feeding an OpenFF 
[`Molecule`] object into a [`BespokeWorkflowFactory`].

[`BespokeOptimizationSchema`]: openff.bespokefit.schema.fitting.BespokeOptimizationSchema
[`BespokeWorkflowFactory`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory

[`Molecule`]: openff.toolkit.topology.Molecule

## The default workflow

The default workflow is suitable for augmenting a general [SMIRNOFF] force field (currently the 
[OpenFF 2.0.0] force field) with a new bespoke torsion term for each non-terminal rotatable bond 
in the input molecule trained to reproduce a bespoke 1D QC torsion scan performed around that bond. 

[SMIRNOFF]: https://openforcefield.github.io/standards/standards/smirnoff/

In this section, we'll build this workflow factory up from nothing. This is just for a demonstration; you can
always build this factory by simply instantiating the `BespokeWorkflowFactory` class without arguments.

The default workflow has three steps:

1. **Fragmentation:** Break the molecule into parts large enough to have accurate
chemistry, but small enough for efficient quantum chemical calculations.
2. **QC Generation:** Perform quantum chemical calculations on the fragments to
generate reference data for the bespoke parameters to reproduce.
3. **Optimization:** Optimize the force field parameters into bespoke parameters
that reproduce the quantum chemical data.

### Fragmentation

BespokeFit uses [OpenFF Fragmenter] to fragment molecules. The fragmenter can be configured by subclasses of 
Fragmenter's [`Fragmenter`] class, which are accepted directly by BespokeFit. By default, a fragmentation scheme that 
aims to ensure the Wiberg bond order of the rotatable bond that the 1D torsion scan is being performed around is the 
same in the parent and the fragment is used:

```python
from openff.fragmenter.fragment import WBOFragmenter

fragmenter = WBOFragmenter()
```

### QC Generation

BespokeFit uses target schemas to define the types of reference data to train the bespoke parameters to. Each target
type has a corresponding QC data type that must be generated as part of the bespoke fitting process to use as a 
reference. A target that measures the deviation between a QC and MM torsion scan, for example, will requre a 1D QC 
torsion scan to be performed. 

The target schema also describes how strongly deviations from the reference data contributes to the overall loss 
function to be minimzed during the optimization stage. Target schema classes are subclasses of [`BaseTargetSchema`], 
and schemas for torsion drives, vibration fitting, and several other targets are available in the 
[`openff.bespokefit.schema.targets`] module.

```python
from openff.bespokefit.schema.targets import TorsionProfileTargetSchema

target = TorsionProfileTargetSchema()
```

We can also specify at how we want to generate any reference data, including the program used, method, basis set, and 
level of theory. This is specified with instances of the [`QCSpec`] class from [QCSubmit]. If multiple specifications 
are provided, the factory will try them in order until it finds one that is both available on the executing machine and 
that supports the target molecule. Note that this may lead to BespokeFit silently behaving differently on machines with 
different software installed.

```python
from openff.qcsubmit.common_structures import QCSpec

qc_spec = QCSpec()
```

[`BaseTargetSchema`]: openff.bespokefit.schema.targets.BaseTargetSchema
[`openff.bespokefit.schema.targets`]: openff.bespokefit.schema.targets
[`QCSpec`]: openff.qcsubmit.common_structures.QCSpec
[QCSubmit]: https://github.com/openforcefield/openff-qcsubmit

### Optimization

BespokeFit optimizers are configured by subclasses of [`BaseOptimizerSchema`]. The default workflow uses [ForceBalance] 
to optimize torsion parameters, so we'll use [`ForceBalanceSchema`] to configure it. The default settings are designed 
for optimizing parameters of an OpenFF force field:

```python
from openff.bespokefit.schema.optimizers import ForceBalanceSchema

optimizer = ForceBalanceSchema()
```

The optimizer also needs an initial force field to use as a starting point. This should be the filename of a force 
field in [offxml format]:

```python
initial_ff = "openff-2.0.0.offxml"
```

Finally, we need to configure hyperparameters that describe the parameter's
priors and how they can be fitted to the reference data. Hyperparameter classes
inherit from [`BaseSMIRKSHyperparameters`]; specific classes for [bonds],
[angles], [proper] and [improper] torsions, and [van der Waals forces] are
available. Since we're only fitting proper torsions, only those hyperparameters
are needed:

```python
from openff.bespokefit.schema.smirnoff import  ProperTorsionHyperparameters

hyperparams = [ProperTorsionHyperparameters()]
```

[`BaseSMIRKSHyperparameters`]: openff.bespokefit.schema.smirnoff.BaseSMIRKSHyperparameters
[bonds]: openff.bespokefit.schema.smirnoff.BondHyperparameters
[angles]: openff.bespokefit.schema.smirnoff.AngleHyperparameters
[proper]: openff.bespokefit.schema.smirnoff.ProperTorsionHyperparameters
[improper]: openff.bespokefit.schema.smirnoff.ImproperTorsionHyperparameters
[van der Waals forces]: openff.bespokefit.schema.smirnoff.VdWHyperparameters

### Putting the factory together

With all the components configured, we can construct the workflow factory with its constructor:

```python
from openff.bespokefit.workflows import BespokeWorkflowFactory

factory = BespokeWorkflowFactory(
    fragmentation_engine = fragmenter,
    target_templates = [target],
    default_qc_specs = [qc_spec],
    optimizer = optimizer,
    initial_force_field = initial_ff,
    parameter_hyperparameters = hyperparams,
)
```

Note that the workflow factory has a few more fields so that even more behavior
can be customized; see its [API documentation] for details.

[OpenFF Fragmenter]: https://github.com/openforcefield/openff-fragmenter
[`Fragmenter`]: openff.fragmenter.fragment.Fragmenter
[ForceBalance]: https://github.com/leeping/forcebalance
[`ForceBalanceSchema`]: openff.bespokefit.schema.optimizers.ForceBalanceSchema
[OpenFF 2.0.0]: https://openforcefield.org/force-fields/force-fields/#sage
[`BaseOptimizerSchema`]: openff.bespokefit.schema.optimizers.BaseOptimizerSchema
[offxml format]: https://openforcefield.github.io/standards/standards/smirnoff/
[API documentation]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory

## Sharing a workflow factory

It's very important to be able to share a customized workflow factory, both so that 
any results produced can be reproducibly documented in the scientific literature and so
that we can be sure we're using the same procedure on different molecules at different
times. Workflow factories can be saved to disk with the [`to_file()`] method:

```python
factory.to_file("my_bespoke_workflow.json")
```

The resulting JSON file can be distributed with a paper or pre-print, or shared
with colleagues. Exported factories can then be used either with the
[`BespokeWorkflowFactory.from_file()`] class method:

```python
from openff.bespokefit.workflows import BespokeWorkflowFactory
factory = BespokeWorkflowFactory.from_file("my_bespoke_workflow.json")
```

[`to_file()`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.to_file
[`BespokeWorkflowFactory.from_file()`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.from_file
