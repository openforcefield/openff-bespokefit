(bespoke_results_chapter)=
# Retrieving results

The current status of a bespoke fit can be retrieved from a bespoke executor in two ways.
From the command line interface:

```shell
openff-bespoke executor retrieve --id          "1"                \
                                 --output      "output.json"      \
                                 --force-field "bespoke-ff.offxml"
```

:::{warning}
A force field file will only be saved if the fit has successfully finished.
:::

Or using the Python API:

```python
from openff.bespokefit.executor.client import BespokeFitClient, Settings

settings = Settings()
client = BespokeFitClient(settings=settings)

output = client.get_optimization(optimization_id="1")
```

In both cases the output will be stored in a [`BespokeExecutorOutput`] class. When using the command 
line interface, the output is saved to a JSON file that can easily be loaded back into a Python:

```python
from openff.bespokefit.executor import BespokeExecutorOutput
output = BespokeExecutorOutput.parse_file("output.json")
```

The class has several attributes that contain information about the ongoing (or potentially finished) bespoke
fit, including the current status, any error message that was raised during the fit, and the final bespoke
force field if the fit finished successfully:

```python
print(output.status)
print(output.error)
force_field = output.bespoke_force_field
```

If the `bespoke_force_field` returned is `None`, it is likely that either the fit is still running or an error was
raised. You should consult the `status` and `error` fields for extra details in this case.

## Combining force fields

Once a set of bespoke fit optimizations have completed, you may want to create a single bespoke force field that can be
applied to this set of molecules. This maybe useful, for example, when studying a congeneric series using relative free
energy calculations. A single force field can be created from a mix of multiple local files and task IDs from the
command line interface:

```shell
openff-bespoke combine --output "combined_forcefield.offxml"  \
                       --ff     "bespoke-ff.offxml"           \
                       --id     "2"                           \
                       --ff     "other-bespoke-ff.offxml"     \
                       --id     "3" 
```

[`BespokeExecutorOutput`]: openff.bespokefit.executor.executor.BespokeExecutorOutput
