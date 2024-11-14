(quick_start_chapter)=
# Quick start

:::{warning}
To reduce runtime, this "Quick start" guide uses a fast semiempirical model, "GFN2-xTB", 
to generate training data, 
rather than the ["default" method](default_qc_method) used to train mainline OpenFF force fields.
:::

BespokeFit aims to provide an automated pipeline to augment a molecular mechanics force field with highly specific force
field parameters trained to accurately capture the important features and phenomenology of an input set of molecules.
It produces bespoke torsion parameters that have been trained to capture as closely as possible the torsion profiles of
the rotatable bonds in the target molecule, which collectively have a large impact on conformational preferences.

The recommended way to install `openff-bespokefit` is via the `mamba` package manager. There are several optional
dependencies, and a good starting environment is:

```shell
mamba create -n bespokefit -y -c conda-forge mamba python=3.10
mamba activate bespokefit 
mamba install -y -c conda-forge openff-bespokefit xtb-python ambertools 
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

### One-off fits

The `run` command is most useful if you are wanting to perform a quick one-off bespoke fit for a single molecule using
a temporary [bespoke executor](executor_chapter).

:::{warning}
You should only have one `run` command running at once. If you want to compute bespoke parameters for multiple 
molecules at once see the [section on production fits](production_fits_section). 
:::

It will accept either a SMILES pattern:

```shell
openff-bespoke executor run --smiles             "CC(=O)NC1=CC=C(C=C1)O" \
                            --workflow           "default"               \
                            --output             "acetaminophen.json"    \
                            --output-force-field "acetaminophen.offxml"  \
                            --n-qc-compute-workers 2                     \
                            --qc-compute-n-cores   1                     \
                            --default-qc-spec xtb gfn2xtb none
```

Or the path to an SDF (or similar) file:

```shell
openff-bespoke executor run --file               "acetaminophen.sdf"    \
                            --workflow           "default"              \
                            --output             "acetaminophen.json"   \
                            --output-force-field "acetaminophen.offxml" \
                            --n-qc-compute-workers 2                    \
                            --qc-compute-n-cores   1                    \
                            --default-qc-spec xtb gfn2xtb none
```

The `run` command also takes arguments defining how the bespoke fit should be performed and parallelized.

:::{note}
Sometimes bespoke commands will raise `RuntimeError: The gateway could not be reached`. This can usually be resolved
by rerunning the command a few times. 
:::

Here we have specified that we wish to start the fit from the general OpenFF 2.2.0 (Sage) force field, augmenting
it with bespoke parameters generated according to the 
[default built-in workflow using GFN2-xTB reference data](workflow_chapter). 

Other available workflows can be viewed by running `openff-bespoke executor run --help`, and the path to a 
[saved workflow factory](quick_start_config_factory) can also be provided using the `--workflow-file` flag.
Alternatively, certain options defined by the workflow can be overridden from the CLI. For example, the default
specification to use for any new QC calculations can be specified using the `--default-qc-spec` flag, e.g.
`--default-qc-spec xtb gfn2xtb none`. See the `--help` for other available overrides.

By default, BespokeFit will use create a single worker for each step in the fitting workflow (i.e. one for fragmenting 
larger molecules, one for generating any needed reference QC data, and one for doing the final bespoke fit), however 
extra workers can easily be requested to speed things up:

```shell
openff-bespoke executor run --file                 "acetaminophen.sdf" \
                            --workflow             "default"           \
                            --n-fragmenter-workers 2                   \
                            --n-optimizer-workers  2                   \
                            --n-qc-compute-workers 2                   \
                            --qc-compute-n-cores   1                   \
                            --default-qc-spec xtb gfn2xtb none
```

:::{note}
For XTB (only), `--qc-compute-n-cores` is ignored because of miscommunications between QCEngine and XTB, but this can be worked around by setting the environment variable `OMP_NUM_THREADS`. See the FAQ for details.
:::

See the chapter on the [bespoke executor](executor_chapter) for more information about parallelizing fits.

(production_fits_section)=
### Production fits

To create bespoke parameters for multiple molecules, such as a particular lead series, it is recommended to instead
launch a dedicated bespoke executor. This allows BespokeFit to re-use data from previous fits, such as common QC
calculations, and easily retrieve previous bespoke fits.

The first step is to launch a [bespoke executor](executor_chapter). The executor is the workhorse of BespokeFit; it 
coordinates every step of the fitting workflow from molecule fragmentation to QC data generation:

```shell
openff-bespoke executor launch --n-fragmenter-workers 1 \
                               --n-optimizer-workers  2 \
                               --n-qc-compute-workers 4 \
                               --qc-compute-n-cores   1
```

The number of workers dedicated to each bespoke fitting stage can be configured here. In general, we recommend devoting 
most of your compute power to the QC compute stage, as this stage is both the most expensive and the most 
parallelizable. See the chapter on the [bespoke executor](executor_chapter) for more information about parallelizing 
fits.

Once the executor has been launched, we can submit molecules to the executor for optimization with the `submit`
command. Molecules can be specified either in the form of a SMILES pattern:

```shell
openff-bespoke executor submit --smiles      "CC(=O)NC1=CC=C(C=C1)O" \
                               --workflow    "default"               \
                               --default-qc-spec xtb gfn2xtb none
```

Or by loading the molecule from an SDF (or similar) file:

```shell
openff-bespoke executor submit --file        "acetaminophen.sdf"   \
                               --workflow    "default"             \
                               --default-qc-spec xtb gfn2xtb none
```

The `submit` command also accepts a combination of the two input forms, as well as multiple occurrences of either. After
the molecules are successfully submitted, the executor will print a table which maps a unique molecule ID to each
molecule SMILES or input file. These IDs can later be used to query the executor about the molecule. This table can be
saved to a .CSV file by adding the `--save-submission-info` flag to the command.

A particular fitting procedure can be monitored with the `watch` command: 

```shell
openff-bespoke executor watch --id "1"
```

A full list of submissions currently being processed can be printed with the `list` command:

```shell
openff-bespoke executor list
```

`list` can be filtered by status; for example, if you would only like to inspect those that have failed:

```shell
openff-bespoke executor list --status errored
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

For users who prefer Python or who are looking for more control over how the fit will be performed, BespokeFit exposes a
full Python API.

:::{note}
These quickstart instructions are for running in a jupyter notebook. If you'd instead like to run this as standard python 
script from the command line, put all this code inside a `def main():` block, and conclude the script with 
`if __name__ == "__main__": main()`. 
:::


At the heart of the fitting pipeline is the [`BespokeWorkflowFactory`]. The [`BespokeWorkflowFactory`] encodes all of
the settings that will feed into and control the bespoke fitting pipeline for *any* input molecule. The workflow
factory transforms a particular molecule into a [workflow](workflow_chapter), which fully describes how bespoke
parameters will be generated for *that specific* molecule:

```python
from openff.bespokefit.workflows import BespokeWorkflowFactory
from openff.qcsubmit.common_structures import QCSpec

factory = BespokeWorkflowFactory(
    # Define the starting force field that will be augmented with bespoke 
    # parameters.
    initial_force_field="openff-2.2.0.offxml",
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


Similar to the previous steps, here we override the default 
["default" QC specification](default_qc_method) to use GFN2-xTB. If we had Psi4
installed, we could remove the `default_qc_specs` argument and the factory would instead use our mainline
[fitting QC method](default_qc_method). 
The default factory will produce [workflows](workflow_chapter) that augment the OpenFF 2.2.0 force field
with bespoke torsion parameters for all non-terminal *rotatable* bonds in the molecule that have been trained 
to quantum chemical torsion scan data generated for said molecule.

:::{note}
See the [configuration section](quick_start_config_factory) for more info on customizing the workflow factory.
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

This schema encodes the full workflow that will produce the bespoke parameters for this specific molecule, including how
any reference QC data should be generated and at what level of theory, the types of bespoke parameters to generate,
hyperparameters defining how they should be trained, and the sequence of fitting steps that should be performed (e.g. fit
a charge model, then re-fit the torsion and valence parameters using the new charge model).

Such a schema is fed into a [`BespokeExecutor`] that will run the full workflow:

```python
from openff.bespokefit.executor import BespokeExecutor, BespokeWorkerConfig
from openff.bespokefit.executor.client import BespokeFitClient, Settings

# create a client to interface with the executor
settings = Settings()
client = BespokeFitClient(settings=settings)

with BespokeExecutor(
    n_fragmenter_workers = 1,
    n_optimizer_workers = 1,
    n_qc_compute_workers = 2,
    qc_compute_worker_config=BespokeWorkerConfig(n_cores=1)
) as executor:
    # Submit our workflow to the executor
    task_id = client.submit_optimization(input_schema=workflow_schema)
    # Wait until the executor is done
    output = client.wait_until_complete(task_id)

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

There workflow factory is largely customizable in order to accommodate different fitting experiments or protocols
that you may wish to use:

```python
from openff.qcsubmit.common_structures import QCSpec

from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.smirnoff import ProperTorsionHyperparameters
from openff.bespokefit.schema.targets import TorsionProfileTargetSchema

factory = BespokeWorkflowFactory(
    # Define the starting force field that will be augmented with bespoke 
    # parameters.
    initial_force_field="openff-2.2.0.offxml",
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
