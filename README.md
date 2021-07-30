BespokeFit
==============================
[//]: # (Badges)
[![CI](https://github.com/openforcefield/bespoke-fit/actions/workflows/CI.yaml/badge.svg)](https://github.com/openforcefield/bespoke-fit/actions/workflows/CI.yaml)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/openforcefield/bespoke-fit.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/openforcefield/bespoke-fit/context:python)
[![codecov](https://codecov.io/gh/openforcefield/bespoke-fit/branch/master/graph/badge.svg)](https://codecov.io/gh/openforcefield/bespoke-fit/branch/master)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Creating bespoke SMIRNOFF format parameters for individual molecules.

This package makes extensive use of fragmentation where ever possible to reduce the computational cost
of torsion scans, optimizations and hessians, as such the `openff-fragmenter` is required along with an openeye license.

Please note that this software in an early and experimental state and unsuitable for production.

### Installation
The required dependencies for `Bespokefit` can be installed using `conda`:

```
conda create --name bespokefit -c conda-forge -c omnia -c omnia/label/rc -c openeye openff-qcsubmit chemper fragmenter==0.0.7 openeye-toolkits forcebalance openforcefield==0.8.0 pydantic==1.7.2
python setup.py develop
```

### Getting Started

#### Building a workflow
In this example we will be building a typical torsion optimization workflow similar to that used in the openff series of forcefields.
The workflow outlines which targets and optimizers will be used along with any reference data generation that should be done such as a torsion drive.

```python
# import the general workflow factory, an optimizer and a target
from openff.bespokefit.workflows import BespokeWorkflowFactory
from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.targets import TorsionProfileTargetSchema

# create the basic factory
workflow = BespokeWorkflowFactory(initial_forcefield="openff_unconstrained-1.3.0.offxml")
# set up the optimizer and any settings
fb = ForceBalanceSchema(penalty_type="L1")
# now create the target with any settings it needs
target = TorsionProfileTargetSchema()
# add these options into the factory
workflow.optimizer = fb
workflow.target_templates = [target]
```
There are now two input options which can be passed to the factory to generate a fitting schema. A fitting schema is a molecule
specific schema which details exactly what tasks are to be done to generate a bespoke forcefield for this molecule
following the protocol in the workflow factory. 

#### Schema from molecules
Here we can pass in a list of openff-toolkit molecules, each molecule will be fragmented 
and a unique fitting task will be generated for each molecule

```python
from openff.toolkit.topology import Molecule
# load some molecules
molecules = Molecule.from_file("molecules.sdf")

# now create the molecule specific fitting schema
schema = workflow.optimization_schemas_from_molecules(molecules=molecules)
```
This schema now has a unique fitting task for each molecule and before fitting requires reference data such as 
optimizations, hessians and torsiondrives. This can be collected by bespokefit using the executor class or the tasks can be 
exported to a `openff-qcsubmit` dataset and submitted to a QCArchive instance manually.

```python
# exporting to a qcsubmit dataset
datasets = schema.build_qcsubmit_datasets()
```

#### Schema from results
Another option is to make a fitting schema from a set of `openff-qcsubmit` results. Once a workflow has been made results can be passed
in, a unique fitting task is then made for each result and the reference data is automatically saved. There is also the option to combine results into one entry
this only makes sense when you want to fit multiple torsions for the same molecule at the same time.

```python
# some results from a qcarchive instance
from openff.qcsubmit.results import TorsionDriveResultCollection
result = TorsionDriveResultCollection.parse_file("results.json")
schema = workflow.fitting_schema_from_results(results=result, combine=True)
```

### Copyright

Copyright (c) 2021, Joshua Horton


#### Acknowledgements
 
Project based on the 
[Computational Molecular Science Python Cookiecutter](https://github.com/molssi/cookiecutter-cms) version 1.1.
