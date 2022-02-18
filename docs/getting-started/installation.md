(installation_chapter)=
# Installation

There are several ways that BespokeFit and its dependencies can be installed, including using the `conda` 
package manager.

## Using conda

The recommended way to install `openff-bespokefit` is via the `conda` package manager:

```shell
conda install -c conda-forge openff-bespokefit
```

### Optional dependencies

#### Psi4

Psi4 is an open source quantum chemistry package that enables BespokeFit to generate bespoke QC data, and is 
recommended to be installed unless you intend to train against data generated using a surrogate such as ANI:

```shell
conda install -c conda-forge -c defaults -c psi4 psi4
```

#### OpenEye toolkits

If you have access to the OpenEye toolkits (namely `oechem`, `oequacpac` and `oeomega`) we recommend installing
these also as these can speed up certain operations significantly.

```shell
conda install -c openeye openeye-toolkits
```

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
