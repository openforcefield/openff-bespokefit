# Release History

Releases follow the ``major.minor.micro`` scheme recommended by
[PEP440](https://www.python.org/dev/peps/pep-0440/#final-releases), where

* `major` increments denote a change that may break API compatibility with previous `major` releases
* `minor` increments add features but do not break API compatibility
* `micro` increments represent bugfix releases or improvements in documentation

<!-- ## Since last release -->

## 0.4.0 / 19-09-2024

### New Features

* [#351] - Adds a `BespokeFitClient` to interface with the executor and support for connecting to executors on a non-local machine [@jthorton]

### Tests updated

* [#338] - Updates a test for QCFractal/QCPortal 0.54. [@mattwthompson]

## 0.3.0 / 27-03-2024

### New Features
* [#280] - Adds support for QCFractal 0.50 and newer [@mattwthompson] [@j-wags] [@ntBre]
* [#334] - Makes test pseudo-private [@mattwthompson]

### Documentation Updates
* [#321] - Documents how to download pre-computed QC data and add it to the local cache, which can avoid the need for local calculcations. by [@jthorton]
* [#325] - Document issue where `xtb` doesn't respect the `--qc-compute-n-cores` argument and provide workaround. by [@mattwthompson]
* [#330] - Corrects a reference to Rosemary, which is not released, in the theory section. by [@mattwthompson]

### Behavior changes
* [#307] - OpenFF 2.2.0 RC1 ("Sage 2.2 RC1") is used as the initial force filed by default (if no other initial force field is specified). by [@mattwthompson]

### Bug fixes
* [#320] - Fixes a formatting issue ([#319]) when printing SMILES to summary table. by [@j-wags]

## 0.2.3 / 14-11-2023

### Bug Fixes
* [#286] - Update for behavior/API changes in ForceBalance 1.9.6 and OFF Tookit 0.14.4. by [@j-wags]

### New Features
* [#272] - Add CLI command to launch workers by [@jhorton]
* [#277] - Allow optimizaitons to run in parallel with torsion drives by [@jhorton]
* [#279] - Allow for re-trying failed QM single-point calculations by [@jhorton]

<!-- ## Version / Date DD-MM-YYYY -->

## 0.2.2 / 08-05-2023

### Bug Fixes
* [#260] - Fix bug where some `import` statements would fail due to circular imports by [@Yoshanuikabundi]

## 0.2.1 / 05-04-2023

### New Features
* [#199] - Add option to always keep temporary files by [@Yoshanuikabundi]

### Bug Fixes
* [#235] - Fix bug where atom indices were incorrectly assigned by [@j-wags]
* [#239] - Fix bug where XTB would fail with a large number of inputs by [@jthorton]

### Documentation Updates
* [#212] - Update Psi4 installation instructions by [@mattwthompson]
* [#226] - Fix typo in theory docs by [@xperrylinn]

## 0.2.0 / 13-12-2022

### New Features

* [#198] - Compatibility OpenFF Toolkit 0.11.x [@Yoshanuikabundi]


## 0.1.3 / 23-11-2022

### Bug Fixes and New Features

* [#193] - Deal with connectivity changes in QC generation [@Yoshanuikabundi]
* [#161] - Create single-file installers [@mattwthompson]

### Documentation Updates

* [#156] - Proofread docs and expand bespoke-workflows [@Yoshanuikabundi]
* [#185] - Update Psi4 installation docs [@mattwthompson]
* [#188] - Update quick start guide with MKL option with XTB [@mattwthompson]
* [#191] - Add issue templates [@mattwthompson]
* [#192] - Add FAQ [@Yoshanuikabundi]


## 0.1.2 / 17-05-2022

### Bug Fixes and New Features

* [#151] - Support single FB jobs [@jthorton]
* [#169] - Fix SMIRNOFF angle prior literal validator [@SimonBoothroyd]
* [#170] - Include non-OpenEye tests in CI [@mattwthompson]

### Documentation Updates

* [#148] - Add XTB to optional dependencies docs [@SimonBoothroyd]
* [#149] - Add ANI install instructions [@jthorton]
* [#147] - Add theory docs suggestions [@SimonBoothroyd]
* [#137] - Add theory page in docs [@Yoshanuikabundi]
* [#172] - Update quick start guide to use Psi4/AmberTools stack [@j-wags]


## 0.1.1 / 18-03-2022

### Bug Fixes

* [#134] - Replace `settings` variable with a function [@SimonBoothroyd]
* [#142] - Deduplicate symmetry equivalent fragments [@jthorton]
* [#144] - Overhaul executor <-> redis interface [@SimonBoothroyd]

### New Features

* [#140] - Multi-molecule submissions via the CLI [@jthorton]
* [#138] - Add CLI override for default bespoke QC spec [@SimonBoothroyd]
* [#143] - Parallel torsiondrives [@jthorton]
* [#145] - Add option to `list` CLI to filter by status [@SimonBoothroyd]
* [#146] - Force field combining [@jthorton]

## 0.1.0 / 23-02-2022

The first major release of bespokefit intended for public use.


[#134]: https://github.com/openforcefield/openff-bespokefit/pull/134
[#137]: https://github.com/openforcefield/openff-bespokefit/pull/137
[#138]: https://github.com/openforcefield/openff-bespokefit/pull/138
[#140]: https://github.com/openforcefield/openff-bespokefit/pull/140
[#142]: https://github.com/openforcefield/openff-bespokefit/pull/142
[#143]: https://github.com/openforcefield/openff-bespokefit/pull/143
[#144]: https://github.com/openforcefield/openff-bespokefit/pull/144
[#145]: https://github.com/openforcefield/openff-bespokefit/pull/145
[#146]: https://github.com/openforcefield/openff-bespokefit/pull/146
[#147]: https://github.com/openforcefield/openff-bespokefit/pull/147
[#148]: https://github.com/openforcefield/openff-bespokefit/pull/148
[#149]: https://github.com/openforcefield/openff-bespokefit/pull/149
[#151]: https://github.com/openforcefield/openff-bespokefit/pull/151
[#156]: https://github.com/openforcefield/openff-bespokefit/pull/156
[#161]: https://github.com/openforcefield/openff-bespokefit/pull/161
[#169]: https://github.com/openforcefield/openff-bespokefit/pull/169
[#170]: https://github.com/openforcefield/openff-bespokefit/pull/170
[#172]: https://github.com/openforcefield/openff-bespokefit/pull/172
[#185]: https://github.com/openforcefield/openff-bespokefit/pull/185
[#188]: https://github.com/openforcefield/openff-bespokefit/pull/188
[#191]: https://github.com/openforcefield/openff-bespokefit/pull/191
[#192]: https://github.com/openforcefield/openff-bespokefit/pull/192
[#193]: https://github.com/openforcefield/openff-bespokefit/pull/193
[#198]: https://github.com/openforcefield/openff-bespokefit/pull/198
[#199]: https://github.com/openforcefield/openff-bespokefit/pull/199
[#212]: https://github.com/openforcefield/openff-bespokefit/pull/212
[#226]: https://github.com/openforcefield/openff-bespokefit/pull/226
[#235]: https://github.com/openforcefield/openff-bespokefit/pull/235
[#239]: https://github.com/openforcefield/openff-bespokefit/pull/239
[#243]: https://github.com/openforcefield/openff-bespokefit/pull/243
[#260]: https://github.com/openforcefield/openff-bespokefit/pull/260
[#272]: https://github.com/openforcefield/openff-bespokefit/pull/272
[#277]: https://github.com/openforcefield/openff-bespokefit/pull/277
[#279]: https://github.com/openforcefield/openff-bespokefit/pull/279
[#280]: https://github.com/openforcefield/openff-bespokefit/pull/280
[#286]: https://github.com/openforcefield/openff-bespokefit/pull/286
[#307]: https://github.com/openforcefield/openff-bespokefit/pull/307
[#320]: https://github.com/openforcefield/openff-bespokefit/pull/320
[#321]: https://github.com/openforcefield/openff-bespokefit/pull/321
[#325]: https://github.com/openforcefield/openff-bespokefit/pull/325
[#330]: https://github.com/openforcefield/openff-bespokefit/pull/330
[#334]: https://github.com/openforcefield/openff-bespokefit/pull/334
[#338]: https://github.com/openforcefield/openff-bespokefit/pull/338
[#351]: https://github.com/openforcefield/openff-bespokefit/pull/351


[@Yoshanuikabundi]: https://github.com/Yoshanuikabundi
[@mattwthompson]: https://github.com/mattwthompson
[@j-wags]: https://github.com/j-wags
[@jthorton]: https://github.com/jthorton
[@SimonBoothroyd]: https://github.com/SimonBoothroyd
[@xperrylinn]: https://github.com/xperrylinn
[@ntBre]: https://github.com/ntBre
