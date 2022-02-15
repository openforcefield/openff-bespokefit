# Reading results

The outcome of a BespokeFit run is reported to the user in instances of the
[`CoordinatorGETResponse`] class. These are returned from the
[`wait_until_complete()`] method of the Python API, or written to the
`output.json` file by the CLI.

If a run has not yet finished, or was unsuccessful, the `results` field of the
report will be `None` (`null` in JSON), and the
[`CoordinatorGETResponse.stages`] field will record which steps were
successful, unsuccessful, or not reached, along with any errors raised.

If a run completed successfully, the [`CoordinatorGETResponse.results`] field
will be populated with the results. A successful run's results are of the type
[`BespokeOptimizationResults`]. While the default workflow has only a single
step, more complex workflows that optimize more than the torsions are broken
into stages. The results of each stage of optimization is stored in the
[`BespokeOptimizationResults.stages`] field as an
[`OptimizationStageResults`] instance. The newly refit force field in SMIRNOFF
XML format can be found in the last stage:

```python
//  from openff.bespokefit.schema.results import BespokeOptimizationResults, OptimizationStageResults
//  results = BespokeOptimizationResults(stages=[OptimizationStageResults()])
results.stages[-1].refit_force_field
```

:::{note} 
Many important fields of the [`BespokeOptimizationResults`] model are
documented in its superclass, [`BaseOptimizationResults`].
:::

[`CoordinatorGETResponse`]: openff.bespokefit.executor.services.coordinator.models.CoordinatorGETResponse
[`CoordinatorGETResponse.parse_file()`]: pydantic.BaseModel.parse_file
[`CoordinatorGETResponse.from_file()`]: openff.bespokefit.executor.services.coordinator.models.CoordinatorGETResponse.from_file
[`wait_until_complete()`]: openff.bespokefit.executor.wait_until_complete
[`CoordinatorGETResponse.results`]:openff.bespokefit.executor.services.coordinator.models.CoordinatorGETResponse.results
[`CoordinatorGETResponse.stages`]:openff.bespokefit.executor.services.coordinator.models.CoordinatorGETResponse.stages
[`BespokeOptimizationResults`]: openff.bespokefit.schema.results.BespokeOptimizationResults
[`BaseOptimizationResults`]: openff.bespokefit.schema.results.BaseOptimizationResults
[`BespokeOptimizationResults.stages`]: openff.bespokefit.schema.results.BaseOptimizationResults.stages
[`OptimizationStageResults`]: openff.bespokefit.schema.results.OptimizationStageResults
