# Contributing to BespokeFit

OpenFF BespokeFit developers follow a [code of conduct]. Please familiarize yourself with the code.

Despite being developed primarily by UK and Australian developers, BespokeFit uses US English in all documentation.

BespokeFit is developed in the open at [GitHub]. We welcome PRs and issues from the general public! Please consider raising an issue there to discuss changes or additions to the code before you commit time to a PR!

A development environment for BespokeFit can be created using [Mamba], which is a faster implementation of the [Conda] package manager:

```shell
git clone https://github.com/openforcefield/openff-bespokefit.git
cd openff-bespokefit
mamba env create --file devtools/conda-envs/test-env.yaml --name bespokefit-dev
mamba env update --file devtools/conda-envs/docs-env.yaml --name bespokefit-dev
mamba activate bespokefit-dev
pip install -e .
```

With this environment, tests can be run locally with [PyTest]:

```shell
pytest openff/bespokefit/tests
```

And documentation can be built with [Sphinx] and viewed in a web browser:

```shell
sphinx-build -j auto docs docs/_build/html
firefox docs/_build/html/index.html
```

Finally, BespokeFit uses a number of lints and code formatters to help maintain code quality. These will be run automatically on any PRs by [pre-commit.ci], so be aware that there's a bot potentially committing to your feature branch. You can run the lints and formatters yourself automatically on each local commit by installing the pre-commit hook:

```shell
mamba install pre-commit -c conda-forge
pre-commit install
```

These hooks are installed in isolated virtual environments, separate from the `conda` environment you created for development (though pre-commit itself will be installed in the current environment). Installing `pre-commit` and hooks locally may help avoid frustration associated with the remote branch coming out of sync when multiple commits are pushed in sequence without pulling the automated changes.

[code of conduct]: CODE_OF_CONDUCT.md
[GitHub]: https://github.com/openforcefield/openff-bespokefit
[Mamba]: https://mamba.readthedocs.io/
[Conda]: https://docs.conda.io/
[PyTest]: https://pytest.org/
[Sphinx]: https://www.sphinx-doc.org/
[pre-commit.ci]: https://results.pre-commit.ci/latest/github/openforcefield/openff-bespokefit/main