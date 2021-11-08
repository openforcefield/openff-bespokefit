# Welcome to BespokeFit's documentation!

:::{toctree}
---
maxdepth: 2
caption: "User's Guide"
glob: True
---

userguide/*

:::

<!-- This matches the styling of a toctree caption as of Sphinx 4.2.0 -->
<div class="toctree-wrapper"><p class="caption" role="heading"><span class="caption-text">
API Reference
</span></p></div>

<!--
The autosummary directive renders to rST,
so we must use eval-rst here
-->
:::{eval-rst}
.. autosummary::
   :recursive:
   :caption: API Reference
   :toctree: _autosummary
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
