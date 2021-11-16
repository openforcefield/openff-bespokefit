# Getting started

BespokeFit creates bespoke [SMIRNOFF-format] molecular mechanics force field parameters for small molecules. It is a Python library in the [Open Force Field ecosystem]. BespokeFit uses [automated chemical fragmentation] extensively to achieve computational efficiency and can interface with a wide variety of quantum chemistry software to compute target data for fitting.

[Open Force Field ecosystem]: https://openforcefield.org/software/#core-infrastructure
[SMIRNOFF-format]: https://openforcefield.github.io/standards/standards/smirnoff/
[automated chemical fragmentation]: https://fragmenter.readthedocs.io/en/latest/

## Installation

Please note that BespokeFit is experimental, pre-production software. It does not promise to have a stable API or even to produce correct results. If you find it produces incorrect results, please [file an issue!]

BespokeFit will soon be available on Conda Forge. In the meantime, or for development, it can be installed manually:

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

Update BespokeFit by pulling updates with Git, and updating any changed dependencies:

```sh
cd /path/to/bespoke-fit
git pull
conda env update --file devtools/conda-envs/test-env.yaml --name bespokefit 
```

Remember to activate the `bespokefit` environment before trying to develop with it:

```sh
conda activate bespokefit
```

[file an issue!]: https://github.com/openforcefield/bespoke-fit/issues/new/choose

## Using BespokeFit

BespokeFit provides a [workflow factory] that describes the entire process of computing and fitting a force field parameter. By default, the factory describes a workflow for optimizing the internal torsion parameters of a molecule in the ["Parsley"] Open Force Field with the [Psi4] quantum chemistry package. A script to perform this default optimization is very simple:

```python
from openff.bespokefit.workflows import BespokeWorkflowFactory
from openff.bespokefit.executor import BespokeExecutor, wait_until_complete
from openff.toolkit.topology import Molecule

# Create the workflow factory
factory = BespokeWorkflowFactory()

# Ask the factory to create an optimization workflow for a particular molecule
target_molecule = Molecule.from_smiles("C(C(=O)O)N") # Glycine
target_molecule.generate_conformers(n_conformers=1)
workflow = factory.optimization_schema_from_molecule(molecule=target_molecule)

# Start up the executor, which manages calling out to other programs
with BespokeExecutor(
    n_fragmenter_workers=1, n_qc_compute_workers=1, n_optimizer_workers=1
) as executor:
    # Submit our workflow to the executor
    task = executor.submit(input_schema=workflow)
    # Wait until the executor is done
    out = wait_until_complete(optimization_id=task.id)

# Print out the re-fit force field
print(out.results.refit_force_field)
```

Like most of BespokeFit, [`BespokeWorkflowFactory`] validates its data as it is assigned according to a schema. This means that we get an immediate error when we make a mistake or try to do something that's unsupported. This schema can 

[workflow factory]: openff.bespokefit.workflows.BespokeWorkflowFactory
[`BespokeWorkflowFactory`]: openff.bespokefit.workflows.BespokeWorkflowFactory
["Parsley"]: https://github.com/openforcefield/openff-forcefields/releases/tag/1.3.0
[Psi4]: https://psicode.org/