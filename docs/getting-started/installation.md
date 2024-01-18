(installation_chapter)=
# Installation

BespokeFit and its dependencies can be installed in several ways. The OpenFF Initiative recommends using the `mamba` package manager.

## Using Mamba

The recommended way to install `openff-bespokefit` is via the `mamba` package
manager. A working installation also requires at least one package from each of
the two sections below ("Fragmentation Backends" and "Reference Data
Generators")

```shell
mamba install -c conda-forge openff-bespokefit "qcportal <0.50"
```

If you do not have Mamba installed, see the [OpenFF installation documentation](openff.docs:install).

:::{warning}
Some upstream dependencies may not be supported on Apple Silicon. To force `mamba` to use the use of the Rosetta emulation layer, use `CONDA_SUBDIR=osx-64`, which is described in more detail [here](https://docs.openforcefield.org/en/latest/install.html#openff-on-apple-silicon-and-arm).
:::

### Fragmentation Backends

#### AmberTools Antechamber

AmberTools is free and open-source, and can generally be used fragment molecules up to 40 heavy atoms in under 
10 minutes.

```shell
mamba install -c conda-forge ambertools
````

#### OpenEye Toolkits

If you have access to the OpenEye toolkits (namely `oechem`, `oequacpac` and `oeomega`) we recommend installing
these also as they can speed up certain operations significantly. OpenEye software requires a 
[free-for-academics license] to run.

```shell
mamba install -c openeye openeye-toolkits
```

[free-for-academics license]: https://www.eyesopen.com/academic-licensing

### Reference Data Generators

#### Psi4

[Psi4] is an open source quantum chemistry package that enables BespokeFit to generate bespoke QC data, and is 
recommended to be installed unless you intend to train against data generated using a surrogate such as ANI:

```shell
mamba install -c conda-forge/label/libint_dev -c conda-forge psi4 dftd3-python
```

[Psi4]: https://psicode.org/

:::{warning}
There are some incompatibilities between the AmberTools and Psi4 conda packages on macOS, and it may not be possible to create a working conda environment containing both.
:::

:::{note}
Installing Psi4 into an existing environment sometimes fails because of subtle differences in
compiled dependencies found in multiple channels. An alternative is to install everything when
initially creating the environment using, with AmberTools:

```shell
mamba create -n bespokefit-env -c conda-forge/label/libint_dev -c conda-forge  python=3.10 openff-bespokefit "qcportal <0.50" psi4 dftd3-python ambertools
```

or with OpenEye Toolkits:

```shell
mamba create -n bespokefit-env -c conda-forge/label/libint_dev -c conda-forge -c openeye python=3.10 openff-bespokefit "qcportal <0.50" psi4 dftd3-python openeye-toolkits
```

:::

#### XTB

The [`xtb-python`] package gives access to the XTB semi-empirical models produced by the Grimme group, which may be
used as a much faster surrogate when generating QC reference data:

```shell
mamba install -c conda-forge xtb-python
```

[`xtb-python`]: https://github.com/grimme-lab/xtb-python

`xtb-python` can _optionally_ be configured to use MKL as its compute backend by running

```shell
mamba install -c conda-forge xtb-python "libblas=*=*mkl"
```

This likely provides better performance on Intel CPUs. Note that use of the MKL backend may be subject to additional
license agreements with Intel. We currently understand it to be free for use by academics and companies generally, but
it is not strictly open source.


#### TorchANI

[TorchANI] is a PyTorch implementation of the ANI neural network potentials from the Roitberg group that can be used as 
a much faster surrogate when generating QC reference data:

```shell
mamba install -c conda-forge torchani
```

:::{note}
TorchANI potentials are only suitable for molecules with a net neutral charge and have limited element coverage 
consisting of C, H, N, O, S, F and Cl
:::

[TorchANI]: https://github.com/aiqm/torchani

## From source

To install `openff-bespokefit` from source, begin by cloning the repository from 
[GitHub](https://github.com/openforcefield/openff-bespokefit):

```shell
git clone https://github.com/openforcefield/openff-bespokefit
cd openff-bespokefit
```

Create a custom conda environment which contains the required dependencies and activate it:

```shell
mamba env create --name openff-bespokefit --file devtools/conda-envs/test-env.yaml
mamba activate openff-bespokefit
```

Finally, install the package itself into the new environment:

```shell
python -m pip install -e .
```
