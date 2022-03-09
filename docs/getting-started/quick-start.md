(quick_start_chapter)=
# Quick start

BespokeFit aims to provide an automated pipeline that ingests a general molecular force field and a set of 
molecules of interest, and produce a new bespoke force field that has been augmented with highly specific 
force field parameters trained to accurately capture the important features and phenomenology of the input set. 

Such features may include generating bespoke torsion parameters that have been trained 
to capture as closely as possible the torsion profiles of the rotatable bonds in the target molecule 
which have a large impact on conformational preferences.

The recommended way to install `openff-bespokefit` is via the `conda` package manager:

```shell
conda install -c conda-forge openff-bespokefit
```

although [several other methods are available](installation_chapter).

There are two main routes for creating a bespoke force field using BespokeFit: 
[using the command-line interface](quick_start_using_cli) or [using the Python API](quick_start_using_api).

(quick_start_using_cli)=
## Using the CLI

The fastest way to start producing a bespoke force field for your molecule of interest is through the [command-line 
interface]. A full list of the available commands, as well as help about each, can be viewed by running:

```shell
openff-bespoke executor --help 
```

Of particular interest are the `run`, `launch`, `submit`, `retrieve` and `watch` commands.

### One-off fits

The `run` command is most useful if you are wanting to perform a quick one-off bespoke fit for a single molecule using
a temporary [bespoke executor](executor_chapter).

:::{warning}
You should only have one `run` command running at once. If you want to compute bespoke parameters for multiple 
molecules at once see the [section on production fits](production_fits_section). 
:::

It will accept either a SMILES pattern

```shell
openff-bespoke executor run --smiles             "CC(=O)NC1=CC=C(C=C1)O" \
                            --workflow           "default"               \
                            --output             "acetaminophen.json"    \
                            --output-force-field "acetaminophen.offxml"  \
                            --n-qc-compute-workers 2                     \
                            --qc-compute-n-cores   8
```

or the path to an SDF (or similar) file

```shell
openff-bespoke executor run --file               "acetaminophen.sdf"    \
                            --workflow           "default"              \
                            --output             "acetaminophen.json"   \
                            --output-force-field "acetaminophen.offxml" \
                            --n-qc-compute-workers 2                    \
                            --qc-compute-n-cores   8
```

in addition to arguments defining how the bespoke fit should be performed and parallelized.

Here we have specified that we wish to start the fit from the general OpenFF 2.0.0 (Sage) force field, augmenting
it with bespoke parameters generated according to the [default built-in workflow](workflow_chapter). 

:::{note}
Other available workflow can be viewed by running `openff-bespoke executor run --help`, or alternatively, the path to a 
[saved workflow factory](quick_start_config_factory) can also be provided using the `--workflow-file` flag.
:::

By default, BespokeFit will use create a single worker for each step in the fitting workflow (i.e. one for fragmenting 
larger molecules, one for generating any needed reference QC data, and one for doing the final bespoke fit), however 
extra workers can easily be requested to speed things up:

```shell
openff-bespoke executor run --file                 "acetaminophen.sdf" \
                            --workflow             "default"           \
                            --n-fragmenter-workers 1                   \
                            --n-optimizer-workers  1                   \
                            --n-qc-compute-workers 2                   \
                            --qc-compute-n-cores   8
```

See the chapter on the [bespoke executor](executor_chapter) for more information about parallelising fits.

(production_fits_section)=
### Production fits

If you are intending to create bespoke parameters for multiple molecules such as a particular lead series, it is 
recommended to instead launch a dedicated bespoke executor. This has the added benefits of being able to re-use
data from previous fits, such as common QC calculations, and easily retrieve previous bespoke fits.

The first step is to launch a [bespoke executor](executor_chapter). The executor is the workhorse of BespokeFit, and 
seamlessly coordinates every step of the fitting workflow from molecule fragmentation to QC data generation:

```shell
openff-bespoke executor launch --n-fragmenter-workers 1 \
                               --n-optimizer-workers  1 \
                               --n-qc-compute-workers 2 \
                               --qc-compute-n-cores   8
```

The number of workers dedicated to each bespoke fitting stage can be tweaked here. In general, we recommend devoting 
most of your compute power to the QC compute stage as this stage is both the most expensive, and most the 
parallelisable. See the chapter on the [bespoke executor](executor_chapter) for more information about parallelising 
fits.

Once the executor has been launched, we can submit molecules to have bespoke parameters trained by the executor using 
the `submit` command either in the form of a SMILES pattern:

```shell
openff-bespoke executor submit --smiles      "CC(=O)NC1=CC=C(C=C1)O" \
                               --workflow    "default"
```

or loading the molecule from an SDF (or similar) file:

```shell
openff-bespoke executor submit --file        "acetaminophen.sdf"   \
                               --workflow    "default"
```

The `submit` command will also accept a combination of the two input forms as well as multiple occurrences of either. 
After successfully submitting the molecules a table will be printed which maps the unique ID that has been assigned by 
the executor to the submission to the molecule smiles and input file if appropriate. To keep track of submissions we can 
also have the table saved to csv by add the corresponding `--save-submission-info` flag to the command.

The ID's can be used to check on state of the submission:

```shell
openff-bespoke executor watch --id "1"
```

A full list of submissions currently being processes can be printed with the `list` command:

```shell
openff-bespoke executor list
```

Once finished, the final force field can be retrieved using the `retrieve` command:

```shell
openff-bespoke executor retrieve --id          "1"                  \
                                 --output      "acetaminophen.json" \
                                 --force-field "acetaminophen.offxml"
```

See the [results chapter](bespoke_results_chapter) for more details on retrieving the results of a bespoke fit.

(quick_start_using_api)=
## Using the API

For the more Python oriented user, or for users who are looking for more control over how the bespoke fit will be
performed, BespokeFit exposes a full Python API.

At the heart of the fitting pipeline is the [`BespokeWorkflowFactory`]. The [`BespokeWorkflowFactory`] encodes the 
full ensemble of settings that will feed into and control the bespoke fitting pipeline for *any* input molecule, and 
is used to create the workflows that fully describe how bespoke parameters will be generated *for a specific* molecule:

```python
from openff.bespokefit.workflows import BespokeWorkflowFactory

factory = BespokeWorkflowFactory()
```

The default factory will produce [workflows](workflow_chapter) that will augment the OpenFF 2.0.0 force field 
with bespoke torsion parameters for all non-terminal *rotatable* bonds in the molecule that have been trained 
to quantum chemical torsion scan data generated for said molecule using the [Psi4] quantum chemistry package.

:::{note}
See the [configuration section](quick_start_config_factory) for more info on customising the workflow factory.
:::

The workflow factory will ingest any molecule that can be represented by the OpenFF Toolkit's [`Molecule`] class
and produce a [`BespokeOptimizationSchema`] schema:

```python
from openff.toolkit.topology import Molecule

input_molecule = Molecule.from_smiles("C(C(=O)O)N")  # Glycine

workflow_schema = factory.optimization_schema_from_molecule(
    molecule=input_molecule
)
```

This schema encodes the full workflow that will produce the bespoke parameters for *this specific molecule*, including 
details about how any reference QC data should be generated and at what level of theory, the types of bespoke parameters 
to generate and hyperparameters about how they should be trained, and the sequence of fitting steps (e.g. fit a 
charge model, then re-fit the torsion and valence parameters using the new charge model) that should be performed.

Such a schema is fed into a [`BespokeExecutor`] that will run the full workflow:

```python
from openff.bespokefit.executor import BespokeExecutor, BespokeWorkerConfig, wait_until_complete

with BespokeExecutor(
    n_fragmenter_workers = 1,
    n_optimizer_workers = 1,
    n_qc_compute_workers = 2,
    qc_compute_worker_config=BespokeWorkerConfig(n_cores=8)
) as executor:
    # Submit our workflow to the executor
    task_id = executor.submit(input_schema=workflow_schema)
    # Wait until the executor is done
    output = wait_until_complete(task_id)

if output.status == "success":
    # Save the resulting force field to an OFFXML file
    output.bespoke_force_field.to_file("output-ff.offxml")
elif output.status == "errored":
    # OR the print the error message if unsuccessful
    print(output.error)
```

The `BespokeExecutor` not only takes care of calling out to any external programs in your workflow such as when 
generating reference QC data, it also manages spreading a queue of tasks over a pool of worker threads so that fitting 
can be executed efficiently in parallel. The `BespokeExecutor` is described in more detail in 
[its own chapter](executor_chapter).

(quick_start_config_factory)=
### Configuring the workflow factory

There workflow factory is largely customisable in order to accommodate different fitting experiments or protocols
that you may wish to use:

```python
from openff.qcsubmit.common_structures import QCSpec

from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.smirnoff import ProperTorsionHyperparameters
from openff.bespokefit.schema.targets import TorsionProfileTargetSchema

factory = BespokeWorkflowFactory(
    # Define the starting force field that will be augmented with bespoke 
    # parameters.
    initial_force_field="openff-2.0.0.offxml",
    # Select the underlying optimization engine.
    optimizer=ForceBalanceSchema(
        max_iterations=50, penalty_type="L1"
    ),
    # Define the types of bespoke parameter to generate and hyper-parameters 
    # that control how they will be fit, as well as the target reference data 
    # that should be used in the fit.
    parameter_hyperparameters=[ProperTorsionHyperparameters()],
    target_templates=[TorsionProfileTargetSchema()],
    # Change the level of theory that the reference QC data is generated at
    default_qc_specs=[
        QCSpec(
            method="gfn2xtb",
            basis=None,
            program="xtb",
            spec_name="xtb",
            spec_description="gfn2xtb",
        )
    ]
)
```

Once the factory is configured, it can be [saved]

```python
factory.to_file("workflow-factory.yaml") # or .json
```

and [loaded] from disk easily

```python
factory = BespokeWorkflowFactory.from_file("workflow-factory.yaml")
```

This makes it simple to record and share complex configurations. OpenFF recommends making this file available when 
publishing data generated using the outputs of BespokeFit for reproducibility. Factories that have been saved to disk 
can also be used via BespokeFit's [command-line interface].

Check the [API docs](openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory) for full descriptions of the factory's 
configurable options.

[saved]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.to_file
[loaded]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory.from_file
[`BespokeWorkflowFactory`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory
[Psi4]: https://psicode.org/

[`Molecule`]: openff.toolkit.topology.Molecule
[`BespokeOptimizationSchema`]: openff.bespokefit.schema.fitting.BespokeOptimizationSchema
[command-line interface]: cli_chapter
[`BespokeExecutor`]: openff.bespokefit.executor.executor.BespokeExecutor
