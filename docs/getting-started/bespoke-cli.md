(cli_chapter)=
# Commands

BespokeFit provides a full command line interface to its major features under
the alias `openff-bespoke`. The CLI is organised into sub-commands similar to 
`conda`, GROMACS, `git` and `apt`. This CLI is self-documenting via the `--help` 
switch which is available on any subcommand:

```sh
openff-bespoke --help
openff-bespoke executor launch --help
```

The executor can also be configured via [environment variables.](envvars)

See the [quick start](quick_start_chapter) guide for examples of using the CLI.

(cli_ref)=
<!--
The click directive renders to rST,
so we must use eval-rst here
-->
:::{eval-rst}
.. click:: openff.bespokefit.cli:cli
    :prog: openff-bespoke
    :nested: full
:::
