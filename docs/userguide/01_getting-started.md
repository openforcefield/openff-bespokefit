# Getting started

BespokeFit creates bespoke [SMIRNOFF-format] molecular mechanics force field parameters for small molecules. It is a Python library in the [Open Force Field ecosystem]. BespokeFit uses [automated chemical fragmentation] extensively to achieve computational efficiency and can interface with a wide variety of quantum chemistry software to compute ground-truth data.

[Open Force Field ecosystem]: https://openforcefield.org/software/#core-infrastructure
[SMIRNOFF-format]: https://openforcefield.github.io/standards/standards/smirnoff/
[automated chemical fragmentation]: https://fragmenter.readthedocs.io/en/latest/

## Installation

Please note that BespokeFit is experimental, pre-production software. It does not promise to have a stable API or even to produce correct results. If you find it produces incorrect results, please [file an issue!]

BespokeFit will soon be available on Conda Forge. In the meantime, or for development, it can be installed manually:

```sh
# Download the repository
git clone https://github.com/openforcefield/bespoke-fit
cd bespoke-fit
# Create a new conda environment with the development dependencies
conda env create --file devtools/conda-envs/test-env.yaml --name bespokefit
# Activate the new environment
conda activate bespokefit
# Add BespokeFit itself to the environment
python setup.py develop
```

Update BespokeFit by pulling updates with Git, and updating any changed dependencies:

```sh
cd /path/to/bespoke-fit
git pull
conda env update --file devtools/conda-envs/test-env.yaml --name bespokefit 
```

Remember to activate the `bespokefit` environment before trying to develop with it:

```sh
conda activate bespokefit
```

[file an issue!]: https://github.com/openforcefield/bespoke-fit/issues/new/choose