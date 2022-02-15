(bespoke_results_chapter)=
# Retrieving results

The current status of a bespoke fit can be retrieved from a bespoke executor in two ways:
from the command line interface

```shell
openff-bespoke executor retrieve --id "1" \
                                 --output "output.json" \
                                 --force-field "bespoke-ff.offxml"
```

:::{note}
A force field file will only be saved if the fit has successfully finished.
:::

or using the Python API

```python
from openff.bespokefit.executor import BespokeExecutor
output = BespokeExecutor.retrieve(optimization_id="1")
```

In both cases the output will be stored in a [`BespokeExecutorOutput`] class. When using the command 
line interace, the output is saved to a JSON file that can easily be loaded back into a Python:

```python
from openff.bespokefit.executor import BespokeExecutorOutput
output = BespokeExecutorOutput.parse_file("output.json")
```

The class has several attributes that contain information about the on-going (or potentially finished) bespoke
fit, including the current status

```python
print(output.status)
```

any error message that was raised during the fit

```python
print(output.error)
```

and the final bespoke force field if the fit has finished

```python
force_field = output.bespoke_force_field
```

If the ``bespoke_force_field`` returned is ``None``, it is likely that either the fit is still running 
or an error was raised. You should consult the ``status`` and ``error`` fields for extra details in this
case.

[`BespokeExecutorOutput`]: openff.bespokefit.executor.executor.BespokeExecutorOutput
