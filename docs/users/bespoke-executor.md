(executor_chapter)=
# BespokeExecutor

BespokeFit not only provides tools and schemas for specifying workflows, but
also an execution environment for running them. This environment is called
[BespokeExecutor]. BespokeExecutor combines a HTTP server, job queue,
parallel scheduler, and workflow interpreter so that workflows produced by
BespokeFit can be efficiently executed in parallel.

BespokeExecutor runs in the background on a computer with plenty of CPU power.
This might be a local workstation or a remote HPC cluster. It then provides a
server to which jobs can be submitted. Submitted jobs are placed in a queue
until resources become available, at which point the executor runs them.
BespokeExecutor breaks workflows down into stages, and runs stages from
different workflows in parallel. This means that even serial steps can take
advantage of the host platform's parallelism, so long as several workflows are
submitted to a single BespokeExecutor instance.

BespokeExecutor can be started, jobs submitted, and progress reported on from
Python code using the [`BespokeExecutor`] class, or from the CLI.

[BespokeExecutor]: openff.bespokefit.executor.executor.BespokeExecutor
[`BespokeExecutor`]: openff.bespokefit.executor.executor.BespokeExecutor

## From Python

Configure the `BespokeExecutor` instance by specifying the number of worker
threads to prepare for each category of tasks. For example, a reasonable
configuration for a quad core workstation might be:

```python
from openff.bespokefit.executor import BespokeExecutor

executor = BespokeExecutor(
    n_fragmenter_workers = 1,
    n_qc_compute_workers = 1,
    n_optimizer_workers = 2,
)
```

Note that `n_qc_compute_workers` only controls `BespokeExecutor`, and the
quantum chemistry code may spin up threads of its own. As a result, using a
large value for `n_qc_compute_workers` may end up over-subscribing the
available cores, even if only one workflow is submitted. If a value greater
than 1 is provided, each worker can work on its own fragment of the target
molecule. The default is to assign 1 worker to each task.

The resulting executor is a context manager that accepts workflows via its
`submit()` method. Recall that workflows are instances of the
[`BespokeOptimizationSchema`] class, which are created by the
[`optimization_schema_from_molecule()`] method on [`BespokeWorkflowFactory`]. As
soon as the context manager ends, the `BespokeExecutor` instance is closed,
terminating any running jobs. To complete a job, we need to use the
`wait_until_complete()` function, which blocks progress in the script until it
can return a result. This is also the easiest way to get results out of the
executor:

```python
//  from openff.bespokefit.executor import BespokeExecutor, wait_until_complete
//  from openff.bespokefit.workflows import BespokeWorkflowFactory
//  from openff.toolkit.topology import Molecule 
//  factory = BespokeWorkflowFactory()
//  target_molecule = Molecule.from_smiles("C(C(=O)O)N") # Glycine
//  workflow = factory.optimization_schema_from_molecule(
//      molecule=target_molecule,
//  )
//  
    with BespokeExecutor(1, 1, 2) as executor:
        task = executor.submit(workflow)
        results = wait_until_complete(task.id).results
```

These functions respectively correspond to a HTTP POST and GET request, and they
return the appropriate [POST] and [GET] response types. [`wait_until_complete()`]
returns the result of a task even if the task has already finished when the
function is executed, so using the context manager with multiple workflows is
simple. Given an iterator of workflow schemas named `workflows`:

```python
//  from openff.bespokefit.executor import BespokeExecutor
//  from openff.bespokefit.workflows import BespokeWorkflowFactory
//  from openff.toolkit.topology import Molecule
//  
//  factory = BespokeWorkflowFactory()
//  smiles = [
//      "C(C(=O)O)N",
//      "CC(C(=O)O)N",
//      "C(C(C(=O)O)N)S",
//  ]
//  molecules = [Molecule.from_smiles(s, allow_undefined_stereo=True) for s in smiles]
//  workflows = [factory.optimization_schema_from_molecule(m) for m in molecules]
    with BespokeExecutor(1, 1, 2) as executor:
        tasks = [executor.submit(w) for w in workflows]
        results = [wait_until_complete(t.id).results for t in tasks]
```

This will return all the results in the same order as the `molecule` iterator,
even if they are executed out of order behind the scenes.

[`BespokeOptimizationSchema`]: openff.bespokefit.schema.fitting.BespokeOptimizationSchema
[`optimization_schema_from_molecule()`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.optimization_schema_from_molecule
[`BespokeWorkflowFactory`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory
[`submit()`]: openff.bespokefit.executor.BespokeExecutor.submit
[`wait_until_complete()`]: openff.bespokefit.executor.wait_until_complete
[POST]: openff.bespokefit.executor.services.coordinator.models.CoordinatorPOSTResponse
[GET]: openff.bespokefit.executor.services.coordinator.models.CoordinatorGETResponse
[`Molecule`]: openff.toolkit.topology.Molecule

## From the CLI

BespokeFit also provides a [command line interface](cli_chapter) for working
with BespokeExecutor. First, start the executor:

```sh
openff-bespoke executor launch
```

Then submit a molecule from a SMILES string:

```sh
openff-bespoke executor submit --smiles "C[C@@H](C(=O)O)N"
```

Note that enough information must be provided to unambiguously construct a
stereochemical molecular graph. In particular, this means that any chiral
centers or nonzero formal charges must be specified. Hydrogens may be included
explicitly or implicitly.

Molecules may also be submitted from a chemical structure file:

```sh
openff-bespoke executor submit --input molecule.sdf
```

The `--input` switch accepts most commonly used chemistry formats. OpenFF
recommends SDF or MOL as they include all the information needed to
unambiguously construct a stereochemical molecular graph. For more information,
see the [OpenFF Toolkit FAQ]. For other options and features, use the `--help`
switch on any subcommand:

```sh
openff-bespoke --help
openff-bespoke executor --help
openff-bespoke executor submit --help # etc
```

[command line interface]: cli_chapter
[OpenFF Toolkit FAQ]: openff.toolkit:faq