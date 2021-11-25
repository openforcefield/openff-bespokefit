(cli_chapter)=
# The BespokeFit Command Line Interface

BespokeFit provides a command line interface to its major features called
`openff-bespoke`. The CLI is organised into sub-commands, similar to Conda,
GROMACS, git and apt. This CLI is self-documenting via the `--help` switch,
which is available on any subcommand:

```sh
openff-bespoke --help
openff-bespoke executor launch --help
```

This help is also available on the [CLI reference] page.

The BespokeFit CLI can submit jobs to and control [`BespokeExecutor`], and 
can also produce input files for manually running optimizations, but does
not support designing new workflow factories; for that, see [](factory_chapter) 
and the API reference page for [`BespokeWorkflowFactory`].


[CLI reference]: cli_ref
[`BespokeExecutor`]: executor_chapter
[`BespokeWorkflowFactory`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory
