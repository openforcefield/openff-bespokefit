# OpenFF BespokeFit

BespokeFit is an automated solution for creating bespoke force field parameters for 
small molecules of interest in the [SMIRNOFF-format] that can be used seamlessly with
more general force fields (such as Parsley and Sage) that are based on SMIRNOFF. 

It is a Python library in the [Open Force Field ecosystem] that emphasises:

* **accuracy**: by training highly specific force field parameters to data that is bespoke
  to molecules that are of most interest, such as candidate drug molecules, a much higher level
  of accuracy can be achieved than a general force field will achieve

* **efficiency**: built-in advanced techniques such as [automated chemical fragmentation] enable
  the framework to rapidly generate bespoke quantum chemical training data at a fraction of the cost 
  while retaining accuracy without any additional user intervention

* **ease of use**: bespoke fitting using well tested, opinionated default settings can be easily performed
  directly from the command line without touching a line of Python 

:::{warning}
Please note that BespokeFit is under continuous development. It does
not promise to have a stable API and may in cases produce inaccurate results. 
We are always looking to improve this framwork so if you do find any undesirable 
or irritating behaviour, please [file an issue!]
:::

[Open Force Field ecosystem]: https://openforcefield.org/software/#core-infrastructure
[SMIRNOFF-format]: https://openforcefield.github.io/standards/standards/smirnoff/
[automated chemical fragmentation]: https://fragmenter.readthedocs.io/en/latest/
[file an issue!]: https://github.com/openforcefield/openff-bespokefit/issues/new/choose

:::{toctree}
---
maxdepth: 2
caption: "Getting Started"
glob: True
hidden: True
---

getting-started/installation
getting-started/quick-start
getting-started/bespoke-cli
FAQ <getting-started/faq.md>

:::


:::{toctree}
---
maxdepth: 2
caption: "Bespoke User Guide"
glob: True
hidden: True
---

users/theory
users/bespoke-workflows
users/bespoke-executor
users/bespoke-results

:::

<!--
The autosummary directive renders to rST,
so we must use eval-rst here
-->
:::{eval-rst}
.. autosummary::
   :recursive:
   :caption: API Reference
   :toctree: ref/api
   :nosignatures:

   openff.bespokefit
:::

:::{toctree}
---
maxdepth: 2
caption: "Developer Guide"
glob: True
hidden: True
---

developers/schemas
releasehistory

:::
