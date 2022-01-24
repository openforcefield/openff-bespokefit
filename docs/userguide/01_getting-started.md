(getting_started_chapter)=
# Getting started

BespokeFit creates bespoke [SMIRNOFF-format] molecular mechanics force field
parameters for small molecules. It is a Python library in the [Open Force Field
ecosystem]. BespokeFit uses [automated chemical fragmentation] extensively to
achieve computational efficiency and can interface with a wide variety of
quantum chemistry software to compute target data for fitting.

[Open Force Field ecosystem]: https://openforcefield.org/software/#core-infrastructure
[SMIRNOFF-format]: https://openforcefield.github.io/standards/standards/smirnoff/
[automated chemical fragmentation]: https://fragmenter.readthedocs.io/en/latest/

## Installation

Please note that BespokeFit is experimental, pre-production software. It does
not promise to have a stable API or even to produce correct results. If you
find it produces incorrect results, please [file an issue!]

BespokeFit will soon be available on Conda Forge. In the meantime, or for
development, it can be installed manually:

```sh
# Download the repository
git clone https://github.com/openforcefield/bespoke-fit
cd bespoke-fit
# Create a new conda environment with the development dependencies
conda env create --file devtools/conda-envs/test-env.yaml --name bespokefit
# Activate the new environment
conda activate bespokefit
# Add BespokeFit itself to the environment
python setup.py develop
```

Update BespokeFit by pulling updates with Git, and updating any changed
dependencies:

```sh
cd /path/to/bespoke-fit
git pull
conda env update --file devtools/conda-envs/test-env.yaml --name bespokefit 
```

Remember to activate the `bespokefit` environment before trying to use it:

```sh
conda activate bespokefit
```

[file an issue!]: https://github.com/openforcefield/bespoke-fit/issues/new/choose

## Using BespokeFit

BespokeFit provides a [workflow factory] that describes the entire process of
computing and fitting a force field parameter. By default, the factory
describes a workflow for optimizing the internal torsion parameters of a
molecule in the ["Parsley"] Open Force Field with the [Psi4] quantum chemistry
package. A script to perform this default optimization is very simple:

```python
    from openff.bespokefit.workflows import BespokeWorkflowFactory
    from openff.bespokefit.executor import BespokeExecutor, wait_until_complete
    from openff.toolkit.topology import Molecule
    
    # Create the workflow factory
    factory = BespokeWorkflowFactory()
    
//  # Use xtb in the doctests for speed
//  from openff.qcsubmit.common_structures import QCSpec
//  xtb_spec = QCSpec(
//      method="gfn2xtb",
//      basis=None,
//      program="xtb",
//      spec_name="xtb",
//      spec_description="gfn2xtb",
//  )
//  factory.default_qc_specs = [xtb_spec]
// 
    # Ask the factory to create an optimization workflow for a given molecule
    target_molecule = Molecule.from_smiles("C(C(=O)O)N") # Glycine
    workflow = factory.optimization_schema_from_molecule(
        molecule=target_molecule,
    )
    
    # Start up the executor, which manages calling out to other programs
    with BespokeExecutor() as executor:
        # Submit our workflow to the executor
        task = executor.submit(input_schema=workflow)
        # Wait until the executor is done
        results = wait_until_complete(optimization_id=task.id).results
    
    # Print out the resulting force field in OFFXML format
    print(results.refit_force_field)
```

[`BespokeWorkflowFactory`] supports a range of options to customize the
workflows it produces. Like most of BespokeFit, [`BespokeWorkflowFactory`] 
validates its data as it is assigned according to a schema. This means that we
get an immediate error when we make a mistake or try to do something that's 
unsupported:

```python
//  from openff.bespokefit.workflows import BespokeWorkflowFactory
//  factory = BespokeWorkflowFactory()
//  try:
        factory.initial_force_field = "openff_unimplemented-1.420.0.offxml"
        # Raises OSError: Source openff_unimplemented-1.420.0.offxml could not be read.
//  except OSError:
//      pass
```

Check the [API docs](openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory)
for descriptions of the factory's configurable options. Once the factory is 
configured, it can be [saved] and [loaded] from disk easily:

```python
//  from openff.bespokefit.workflows import BespokeWorkflowFactory
//  factory = BespokeWorkflowFactory()
    factory.to_file("default_factory.yaml") # or .json
    factory_from_disk = BespokeWorkflowFactory.from_file("default_factory.yaml")
    assert factory == factory_from_disk
```

This makes it simple to record and share complex configurations. OpenFF
recommends making this file available when publishing data using BespokeFit for
reproducibility. Factories that have been saved to disk can also be used via
BespokeFit's [command line interface].

The configured factory describes a general workflow for any molecule that can be
represented by the OpenFF Toolkit's [`Molecule`] class. The configured
factory's [`optimization_schema_from_molecule()`] method takes a `Molecule` and
produces a [`BespokeOptimizationSchema`] object. Note that the Toolkit can be
very strict about the kinds of input it accepts, as it wants to avoid
misinterpreting an ambiguous input and silently producing the wrong molecule.
Rather than providing a coordinate file, it's usually best to provide a SMILES
string of the target molecule.

```python
//  from openff.bespokefit.workflows import BespokeWorkflowFactory
//  from openff.toolkit.topology import Molecule
//  factory = BespokeWorkflowFactory()
//  
    target_molecule = Molecule.from_smiles("C(C(=O)O)N") # Glycine
    workflow = factory.optimization_schema_from_molecule(
        molecule=target_molecule,
    )
```

Once we have the target molecule's optimization schema, we use
[`BespokeExecutor`] to run the workflow. `BespokeExecutor` not only takes care
of calling out to any external programs in your workflow, it also manages
spreading a queue of jobs over a pool of worker threads so that batch runs can
be executed efficiently in parallel. `BespokeExecutor` is described in more
detail in [it's own chapter](executor_chapter).

[workflow factory]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory
[`BespokeWorkflowFactory`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory
["Parsley"]: https://github.com/openforcefield/openff-forcefields/releases/tag/1.3.0
[Psi4]: https://psicode.org/
[saved]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.to_file
[loaded]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.from_file
[`Molecule`]: openff.toolkit.topology.Molecule
[`BespokeOptimizationSchema`]: openff.bespokefit.schema.fitting.BespokeOptimizationSchema
[`optimization_schema_from_molecule()`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.optimization_schema_from_molecule
[command line interface]: cli_chapter
[`BespokeExecutor`]: openff.bespokefit.executor.executor.BespokeExecutor