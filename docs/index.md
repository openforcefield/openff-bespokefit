# Welcome to BespokeFit's documentation!

:::{toctree}
---
maxdepth: 2
caption: "User's Guide"
glob: True
---

users/getting-started
users/schemas
users/workflow-factory
users/bespoke-executor
users/results
users/bespoke-cli

:::

:::{toctree}
---
maxdepth: 2
caption: "Command Line Reference"
glob: True
---

ref/cli

:::

(api_ref)=
<!-- This matches the styling of a toctree caption as of Sphinx 4.2.0 -->
<div class="toctree-wrapper"><p class="caption" role="heading"><span class="caption-text">
Python API Reference
</span></p></div>

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



<!-- This matches the styling of a toctree caption as of Sphinx 4.2.0 -->
<div class="toctree-wrapper"><p class="caption" role="heading"><span class="caption-text">
Indices
</span></p></div>

* [](genindex)
* [](modindex)
* [](search)
