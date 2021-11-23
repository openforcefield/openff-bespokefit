(executor_chapter)=
# BespokeExecutor

BespokeFit not only provides tools and schemas for specifying workflows, but
also an execution environment for running them. This environment is called
[`BespokeExecutor`]. `BespokeExecutor` combines a HTTP server, job queue,
parallel scheduler, and workflow interpreter so that workflows produced by
BespokeFit can be efficiently executed in parallel.

`BespokeExecutor` runs in the background on a computer with plenty of CPU power.
This might be a local workstation or a remote HPC cluster. It then provides a
server to which jobs can be submitted. Submitted jobs are placed in a queue
until resources become available, at which point `BespokeExecutor` runs them.
`BespokeExecutor` can break a workflow down into stages and run parts in
parallel with parts from other workflows so that even serial steps can take
advantage of the host platform's parallelism. This means that several workflows
submitted to a single `BespokeExecutor` instance can be faster than the same
workflows submitted to individual instances.

`BespokeExecutor` can be started, jobs submitted, and progress reported on from
Python code using the [`BespokeExecutor`] class, or from the CLI.

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
molecule.

The resulting executor is a context manager that accepts workflows submitted to
it by its `submit()` method. As soon as the context manager ends, the
`BespokeExecutor` instance is closed, terminating any running jobs. To complete
a job, we need to use the `wait_until_complete()` function, which blocks
progress in the script until it can return a result. This is also the easiest
way to get results out of the executor:

```python
//  from openff.bespokefit.executor import BespokeExecutor
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
        result = wait_until_complete(task.id)
```

These functions respectively correspond to a HTTP POST and GET request, and they
return the appropriate [POST] and [GET] response types. Using the context with
multiple workflows is simple:

```python
//  from openff.bespokefit.executor import BespokeExecutor
//  from openff.bespokefit.workflows import BespokeWorkflowFactory
//  from openff.toolkit.topology import Molecule
//  target_molecule = Molecule.from_smiles("C(C(=O)O)N") # Glycine
//  workflow = factory.optimization_schema_from_molecule(
//      molecule=target_molecule,
//  )
//  
//  factory = BespokeWorkflowFactory()
//  smiles = [
//      "C(C(=O)O)N",
//      "CC(C(=O)O)N",
//      "C(C(C(=O)O)N)S",
//  ]
//  molecules = [Molecule.from_smiles(s) for s in smiles]
    workflows = [factory.optimization_schema_from_molecule(m) for m in molecules]
    with BespokeExecutor(1, 1, 2) as executor:
        tasks = [executor.submit(w) for w in workflows]
        results = [wait_until_complete(t.id) for t in tasks]
```


[`BespokeExecutor`]: openff.bespokefit.executor.BespokeExecutor
[`submit()`]: openff.bespokefit.executor.BespokeExecutor.submit
[`wait_until_complete()`]: openff.bespokefit.executor.wait_until_complete
[POST]: openff.bespokefit.executor.services.coordinator.models.CoordinatorPOSTResponse
[GET]: openff.bespokefit.executor.services.coordinator.models.CoordinatorGETResponse