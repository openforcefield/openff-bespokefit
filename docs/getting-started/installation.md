(installation_chapter)=
# Installation

BespokeFit and its dependencies can be installed in several ways. The OpenFF Initiative recommends using the `conda`
package manager.

## Using conda

The recommended way to install `openff-bespokefit` is via the `conda` package manager:

```shell
conda install -c conda-forge openff-bespokefit
```

### Optional dependencies

#### Psi4

[Psi4] is an open source quantum chemistry package that enables BespokeFit to generate bespoke QC data, and is 
recommended to be installed unless you intend to train against data generated using a surrogate such as ANI:

```shell
conda install -c conda-forge -c defaults -c psi4 psi4
```

[Psi4]: https://psicode.org/

#### XTB

The [`xtb-python`] package gives access to the XTB semi-empirical models produced by the Grimme group, which may be
used as a much faster surrogate when generating QC reference data (see [](quick_start_chapter) for more details):

```shell
conda install -c conda-forge xtb-python
```

[`xtb-python`]: https://github.com/grimme-lab/xtb-python

#### TorchANI

[TorchANI] is a pytorch implementation of the ANI neural network potentials from the Roitberg group that can be used as 
a much faster surrogate when generating QC reference data (see [](quick_start_chapter) for more details):

```shell
conda install -c conda-forge torchani
```

:::{note}
TorchANI potentials are only suitable for molecules with a net neutral charge and have limited element coverage 
consisting of C, H, N, O, S, F and Cl
:::

[TorchANI]: https://github.com/aiqm/torchani

#### OpenEye toolkits

If you have access to the OpenEye toolkits (namely `oechem`, `oequacpac` and `oeomega`) we recommend installing
them also, as they can speed up certain operations significantly.

```shell
conda install -c openeye openeye-toolkits
```

## From source

To install `openff-bespokefit` from source, begin by cloning the repository from 
[GitHub](https://github.com/openforcefield/openff-bespokefit):

```shell
git clone https://github.com/openforcefield/openff-bespokefit
cd openff-bespokefit
```

Create a custom conda environment which contains the required dependencies and activate it:

```shell
conda env create --name openff-bespokefit --file devtools/conda-envs/test-env.yaml
conda activate openff-bespokefit
```
Finally, install the package itself:

```shell
python setup.py develop
```
