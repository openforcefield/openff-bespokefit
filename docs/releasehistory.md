# Release History

Releases follow the ``major.minor.micro`` scheme recommended by
[PEP440](https://www.python.org/dev/peps/pep-0440/#final-releases), where

* `major` increments denote a change that may break API compatibility with previous `major` releases
* `minor` increments add features but do not break API compatibility
* `micro` increments represent bugfix releases or improvements in documentation

<!--## Version / Date DD-MM-YYYY -->


## 0.2.0 / 12-13-2022

### New Features

* [#198]: Compatibility OpenFF Toolkit 0.11.x [@Yoshanuikabundi]


## 0.1.3 / 11-23-2022

### Bug Fixes and New Features

* [#193]: Deal with connectivity changes in QC generation [@Yoshanuikabundi]
* [#161]: Create single-file installers [@mattwthompson]

### Documentation Updates

* [#156]: Proofread docs and expand bespoke-workflows [@Yoshanuikabundi]
* [#185]: Update Psi4 installation docs [@mattwthompson]
* [#188]: Update quick start guide with MKL option with XTB [@mattwthompson]
* [#191]: Add issue templates [@mattwthompson]
* [#192]: Add FAQ [@Yoshanuikabundi]


## 0.1.2 / 05-17-2022

### Bug Fixes and New Features

* [#151]: Support single FB jobs [@jthorton]
* [#169]: Fix SMIRNOFF angle prior literal validator [@SimonBoothroyd]
* [#170]: Include non-OpenEye tests in CI [@mattwthompson]

### Documentation Updates

* [#148]: Add XTB to optional dependencies docs [@SimonBoothroyd]
* [#149]: Add ANI install instructions [@jthorton]
* [#147]: Add theory docs suggestions [@SimonBoothroyd]
* [#137]: Add theory page in docs [@Yoshanuikabundi]
* [#172]: Update quick start guide to use Psi4/AmberTools stack [@j-wags]


## 0.1.1 / 03-18-2022

### Bug Fixes

* [#134]: Replace `settings` variable with a function [@SimonBoothroyd]
* [#142]: Deduplicate symmetry equivalent fragments [@jthorton]
* [#144]: Overhaul executor <-> redis interface [@SimonBoothroyd]

### New Features

* [#140]: Multi-molecule submissions via the CLI [@jthorton]
* [#138]: Add CLI override for default bespoke QC spec [@SimonBoothroyd]
* [#143]: Parallel torsiondrives [@jthorton]
* [#145]: Add option to `list` CLI to filter by status [@SimonBoothroyd]
* [#146]: Force field combining [@jthorton]

## 0.1.0 / 02-23-2022

The first major release of bespokefit intended for public use.


[#134]: https://github.com/openforcefield/openff-qcsubmit/pull/134
[#137]: https://github.com/openforcefield/openff-qcsubmit/pull/137
[#138]: https://github.com/openforcefield/openff-qcsubmit/pull/138
[#140]: https://github.com/openforcefield/openff-qcsubmit/pull/140
[#142]: https://github.com/openforcefield/openff-qcsubmit/pull/142
[#143]: https://github.com/openforcefield/openff-qcsubmit/pull/143
[#144]: https://github.com/openforcefield/openff-qcsubmit/pull/144
[#145]: https://github.com/openforcefield/openff-qcsubmit/pull/145
[#146]: https://github.com/openforcefield/openff-qcsubmit/pull/146
[#147]: https://github.com/openforcefield/openff-qcsubmit/pull/147
[#148]: https://github.com/openforcefield/openff-qcsubmit/pull/148
[#149]: https://github.com/openforcefield/openff-qcsubmit/pull/149
[#151]: https://github.com/openforcefield/openff-qcsubmit/pull/151
[#156]: https://github.com/openforcefield/openff-qcsubmit/pull/156
[#161]: https://github.com/openforcefield/openff-qcsubmit/pull/161
[#169]: https://github.com/openforcefield/openff-qcsubmit/pull/169
[#170]: https://github.com/openforcefield/openff-qcsubmit/pull/170
[#172]: https://github.com/openforcefield/openff-qcsubmit/pull/172
[#185]: https://github.com/openforcefield/openff-qcsubmit/pull/185
[#188]: https://github.com/openforcefield/openff-qcsubmit/pull/188
[#191]: https://github.com/openforcefield/openff-qcsubmit/pull/191
[#192]: https://github.com/openforcefield/openff-qcsubmit/pull/192
[#193]: https://github.com/openforcefield/openff-qcsubmit/pull/193
[#198]: https://github.com/openforcefield/openff-qcsubmit/pull/198

[@Yoshanuikabundi]: https://github.com/Yoshanuikabundi
[@mattwthompson]: https://github.com/mattwthompson
[@j-wags]: https://github.com/j-wags
[@jthorton]: https://github.com/jthorton
[@SimonBoothroyd]: https://github.com/SimonBoothroyd
