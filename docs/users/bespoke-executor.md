(executor_chapter)=
# Bespoke executor

The bespoke executor is the main workhorse within BespokeFit. Its role is to ingest and run bespoke fitting workflows, 
namely by coordinating and launching the individual steps within a bespoke fitting workflow (e.g. generating QC 
reference data) without any user intervention across multiple CPUs or even multiple nodes in a cluster.  

The executor operates by splitting the full bespoke workflow into individual stages:

1. **fragmentation**: the input molecule is fragmented into smaller pieces in a way that preserves key features of 
  the input molecule.
2. **QC generation**: any bespoke QC data, for example 1D torsion scans of each rotatable bond in the input molecule, 
   is generated using the smaller fragments for computational efficiency.
3. **optimization**: the reference data, including any bespoke QC data, is fed into the optimizer (e.g. ForceBalance) 
   specified by the workflow schema in order to train the bespoke parameters

Each stage has its own set of 'workers' available to it making it easy to devote more compute where needed. Each worker 
is in essence a program that is assigned a set of local resources, e.g. 2 CPUs, and can be sent a specific task, e.g. 
perform this 1D torsion scan, to run on those resources.

:::{note}
Workers and task scheduling within BespokeFit are handled behind the scenes by the [Celery] framework in combination
with [Redis] which handles any necessary storage of inputs and outputs for each stage.
:::

These workers are created and managed by the executor when it is created, and so most users will not need to worry
about their details too much unless they are wanting to parallelize fits across multiple nodes in a cluster. The only
choice a user needs to make is how many workers to spawn for each stage, and how many compute resources should each type 
of worker be allowed to use.

There are two main ways to launch a bespoke executor: [using the executor command-line interface](executor_using_cli) or 
[using the Python API](executor_using_api).

(executor_using_cli)=
## Using the CLI

A dedicated bespoke executor can be launched using the `launch` command

```shell
openff-bespoke executor launch --directory            "bespoke-executor" \
                               --n-fragmenter-workers 1                  \
                               --n-optimizer-workers  1                  \
                               --n-qc-compute-workers 1
```

By default, the executor will create a single worker for each stage, and will all said worker to access the full 
set of resources on the machine it is running on. If you are spawning multiple workers for a stage, as you likely
will want to for the QC compute stage, it is recommended to also specify the maximum number of cores / CPUs and the 
maximum memory per core that the QC engine (e.g. `psi4`) can consume

```shell
openff-bespoke executor launch --directory            "bespoke-executor" \
                               --n-fragmenter-workers 1                  \
                               --n-optimizer-workers  1                  \
                               --n-qc-compute-workers 2                  \
                               --qc-compute-n-cores   8                  \
                               --qc-compute-max-mem   2.5
```

where here we have request two workers each with access to eight CPUs and with 2.5 GB of memory per CPU (i.e. 16 CPUs in
total and 40 GB of memory). The memory limit is not strictly enforced by the executor, and is instead passed to the 
underlying QC engine as a rough guideline via the [QCEngine] interface.

See the [quick start guide](quick_start_chapter) for details on submitting jobs to a running bespoke executor.

[QCEngine]: http://docs.qcarchive.molssi.org/projects/QCEngine/en/stable/

(executor_using_api)=
## Using the API

A bespoke executor can be created via the Python API through the [`BespokeExecutor`] class:

```python
from openff.bespokefit.executor import BespokeExecutor, BespokeWorkerConfig

executor = BespokeExecutor(
    # Configure the workers that will fragment larger molecules
    n_fragmenter_workers=1,
    fragmenter_worker_config=BespokeWorkerConfig(n_cores=1),
    # Configure the workers that will generate any needed QC
    # reference data such as 1D torsion scans
    n_qc_compute_workers=1,
    qc_compute_worker_config=BespokeWorkerConfig(n_cores="auto"),
    # Configure the workers that will perform the final optimization
    # using the specified engine such as ForceBalance
    n_optimizer_workers=1,
    optimizer_worker_config=BespokeWorkerConfig(n_cores=1),
)
```

The [`BespokeWorkerConfig`] will control how many compute resources are assined to each worker. In the above example 
the fragmenter and optimizer workers are only allowed to use a single core / CPU, while the QC compute worker will 
be allowed to use the full set of CPUs available on the machine (`n_cores="auto"`).

The executor itself is a context manager and will not 'start' until the context is entered:

```python
from openff.bespokefit.executor import wait_until_complete

with executor:
    task_id = BespokeExecutor.submit(workflow)
    output = wait_until_complete(task_id)
```

When an executor 'starts' it will spin up all the required child processes such as the per stage workers and a [Redis] 
instance if requested (by default one will be created).

Within the executor context bespoke fits can be submitted using the [`submit()`] method. As soon as the context manager 
exists the executor instance is closed, terminating any running jobs. To ensure the submission is allowed to finish we 
can use the [`wait_until_complete()`] helper function. This function will block progress in the script until it can 
return a result.

[Celery]: https://docs.celeryproject.org/en/stable/index.html
[Redis]: https://redis.io/

[`submit()`]: openff.bespokefit.executor.BespokeExecutor.submit
[`wait_until_complete()`]: openff.bespokefit.executor.wait_until_complete
[`BespokeExecutor`]: openff.bespokefit.executor.BespokeExecutor
[`BespokeWorkerConfig`]: openff.bespokefit.executor.BespokeWorkerConfig
