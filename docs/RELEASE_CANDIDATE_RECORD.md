# Technical release-candidate record

[Release acceptance](RELEASE_ACCEPTANCE.md) · [Draft release notes](RELEASE_NOTES_DRAFT.md) · [Reviewer guide](REVIEWER_GUIDE.md)

**Tested revision:** [`df3ed236dc46d3ca9f4bcf2521b2dae2ff8e74f2`](https://github.com/fraware/model-claim-replay/commit/df3ed236dc46d3ca9f4bcf2521b2dae2ff8e74f2). Package version 0.1.0. The record applies to this exact revision, not a subsequently edited branch. No tag or package registry publication is asserted.

## Validation evidence

The [mainline suite](https://github.com/fraware/model-claim-replay/actions/runs/45542011721) passed all 12 jobs, including the actual archived evidence tests, Python 3.10/3.12/3.13, source distribution and wheel installation on Linux/macOS/Windows, browser regression, optional integrations and dependency audit. [Provider readiness](https://github.com/fraware/model-claim-replay/actions/runs/45542011815) passed with no inference. The [production deployment check](https://github.com/fraware/model-claim-replay/actions/runs/45537786663) passed at the earlier website revision `507bc68cdddee258967118cd750b1b6928022248`; the subsequent source-index and package-validation changes did not edit website assets.

## Tested package commitments

The three original Actions ZIP files were downloaded and SHA-256 checked against their reported digests. Each embedded verification receipt identifies the tested revision. The byte lengths and SHA-256 hashes of both packages inside each archive were checked independently. All wheel RECORD entries were verified against the included members.

| Runner | Artifact ID | ZIP SHA-256 |
|---|---:|---|
| Linux | 14988724769 | `23059f7b7a1181d52e4a996cf6e629ae0df2d35c5e43a03f69fa4bb38ff93cc9` |
| macOS | 14989023750 | `96cd7f59b1bd9c41870c22a9687d34431a4b5107acad4016dac10922f9252467` |
| Windows | 14988839484 | `c15460040cbe9eced97809280f4c6529dd6d5a05f35f95cecdfd7e1b94fabd9c` |

| Runner | Wheel SHA-256 | Source distribution SHA-256 |
|---|---|---|
| Linux | `edc8d2d3c784b290a344e21a524a291b0aa5ba5eb1a995a8e1f8095a72a92356` | `2d2f1b1eeceb23c6743e76387d3717a8a181077d2158713ed8a156d2b49c4548` |
| macOS | `8fc556914af65acc89175b2ef28d1d1c1cb355dd9c165f526bb94d2b5638c6e5` | `c960e9733622642450e98245f7bd497fae2d1795d9813b37a01a7903f57c16d2` |
| Windows | `81c2206ef45561c59a419d2c182be08361a09fc2aa88551d292349e6e841197e` | `c1c37103ea9444e9379b98a3bdaf6d88eaeb93da2391cee20ef2643ae3d2cea4` |

Each wheel contains 27 file members. All corresponding members match byte-for-byte except METADATA and RECORD; METADATA matches after CRLF-to-LF normalization. Each source distribution contains 73 file members; differences are confined to generated PKG-INFO and setup.cfg. The wheel and source archive hashes differ across runners: byte-identical rebuilds are not established. The original artifacts have finite Actions retention; this record is not a permanent copy of them.

The automated wheel installation, demo execution and verification durations were 1.010 s (Linux), 1.059 s (macOS), and 1.735 s (Windows). These exclude clone, virtual environment creation, package build and opening the HTML report. They are not onboarding times or external sessions.

## Release decision

The tested revision satisfies the automated technical checks. External developer attempts, independent evidence review, original full-answer extraction verification, and third-party provider authentication remain outstanding. No independent reviewer is inferred from maintainer calculations. Before tagging a release, confirm the exact selected revision and its corresponding package artifacts and record any release-gate decisions. Do not reuse artifact commitments for a later revision.
