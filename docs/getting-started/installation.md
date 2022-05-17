(installation_chapter)=
# Installation

There are several ways that BespokeFit and its dependencies can be installed, including using the `conda` 
package manager.

## Using conda

The recommended way to install `openff-bespokefit` is via the `conda` package manager.
A working installation also requires at least one package from each of the two sections below 
("Fragmentation Backends" and "Reference Data Generators")

```shell
conda install -c conda-forge openff-bespokefit
```



### Fragmentation Backends

#### AmberTools Antechamber

AmberTools is free and open-source, and can generally be used fragment molecules up to 40 heavy atoms in under 
10 minutes.

```shell
conda install -c conda-forge ambertools
````

#### OpenEye Toolkits

If you have access to the OpenEye toolkits (namely `oechem`, `oequacpac` and `oeomega`) we recommend installing
these also as they can speed up certain operations significantly. OpenEye software requires a free-for-academics 
license to run.

```shell
conda install -c openeye openeye-toolkits
```

### Reference Data Generators

#### Psi4

Psi4 is an open source quantum chemistry package that enables BespokeFit to generate bespoke QC data, and is 
recommended to be installed unless you intend to train against data generated using a surrogate such as ANI:

```shell
conda install -c conda-forge -c defaults -c psi4 psi4
```

:::{warning}
There is an incompatibility between the AmberTools and Psi4 conda packages on Mac, and it is not possible to
create a working conda environment containing both. 
:::

#### XTB

The xtb package gives access to the XTB semi-empirical models produced by the Grimme group in Bonn which may be used 
as a much faster surrogate when generating QC reference data (see [](quick_start_chapter) for more details):

```shell
conda install -c conda-forge xtb-python
```

#### TorchANI

TorchANI is a pytorch implementation of the ANI neural network potentials from the Roitberg group that can be used as 
a much faster surrogate when generating QC reference data (see [](quick_start_chapter) for more details):

```shell
conda install -c conda-forge torchani
```

:::{note}
TorchANI potentials are only suitable for molecules with a net neutral charge and have limited element coverage 
consisting of C, H, N, O, S, F and Cl
:::

## From source

To install `openff-bespokefit` from source begin by cloning the repository from 
[github](https://github.com/openforcefield/openff-bespokefit),

```shell
git clone https://github.com/openforcefield/openff-bespokefit
cd openff-bespokefit
```

create a custom conda environment which contains the required dependencies and activate it,

```shell
conda env create --name openff-bespokefit --file devtools/conda-envs/test-env.yaml
conda activate openff-bespokefit
```
and finally install the package itself:

```shell
python setup.py develop
```
