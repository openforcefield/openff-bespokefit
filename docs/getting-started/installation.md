(installation_chapter)=
# Installation

BespokeFit and its dependencies can be installed in several ways. The OpenFF Initiative recommends using the `conda`
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
these also as they can speed up certain operations significantly. OpenEye software requires a 
[free-for-academics license] to run.

```shell
conda install -c openeye openeye-toolkits
```

[free-for-academics license]: https://www.eyesopen.com/academic-licensing

### Reference Data Generators

#### Psi4

[Psi4] is an open source quantum chemistry package that enables BespokeFit to generate bespoke QC data, and is 
recommended to be installed unless you intend to train against data generated using a surrogate such as ANI:

```shell
conda install -c psi4 -c conda-forge -c defaults psi4
```

[Psi4]: https://psicode.org/

:::{warning}
There is an incompatibility between the AmberTools and Psi4 conda packages on Mac, and it is not possible to
create a working conda environment containing both. 
:::

:::{note}
Installing Psi4 into an existing environment sometimes fails because of subtle differences in
compiled dependencies found in multiple channels. An alternative is to install everything when
initially creating the environment using, with AmberTools:

```shell
conda create -n bespokefit-env -c psi4 -c conda-forge -c defaults python=3.9 openff-bespokefit psi4 ambertools
```

or with OpenEye Toolkits:

```shell
conda create -n bespokefit-env -c psi4 -c conda-forge -c defaults -c openeye python=3.9 openff-bespokefit psi4 openeye-toolkits
```
:::

#### XTB

The [`xtb-python`] package gives access to the XTB semi-empirical models produced by the Grimme group, which may be
used as a much faster surrogate when generating QC reference data:

```shell
conda install -c conda-forge xtb-python
```

[`xtb-python`]: https://github.com/grimme-lab/xtb-python

`xtb-python` can _optionally_ be configured to use MKL as its compute backend by running

```shell
conda install -c conda-forge xtb-python "libblas=*=*mkl"
```

This likely provides better performance on Intel CPUs. Note that use of the MKL backend may be subject to additional
license agreements with Intel. We currently understand it to be free for use by academics and companies generally, but
it is not strictly open source.


#### TorchANI

[TorchANI] is a PyTorch implementation of the ANI neural network potentials from the Roitberg group that can be used as 
a much faster surrogate when generating QC reference data:

```shell
conda install -c conda-forge torchani
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
conda env create --name openff-bespokefit --file devtools/conda-envs/test-env.yaml
conda activate openff-bespokefit
```
Finally, install the package itself into the new environment:

```shell
python setup.py develop
```
