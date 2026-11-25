# Draft v0.1.0 release notes

**Status: candidate only.** No release tag or PyPI publication is asserted. The technical gates and independent validation requirements are in [release acceptance](RELEASE_ACCEPTANCE.md).

Model Claim Replay is an open-source CLI and static evidence explorer for auditing named AI benchmark claims. The first version includes a dependency-free offline demo, source-linked claim manifests, evidence verification and reporting, a narrow Inspect AI Chartography importer and paired diagnostics, and source-bound GraphWalks tools.

## Research evidence

- 200 public GraphWalks BFS candidate prompts counted with Gemini 4 Neon: 100 fit its reported input limit, 100 exceed it. No Gemini generation.
- One source-bound GPT-6.2 Sol diagnostic: disclosed-line F1 1.0.
- Separate 16-task GPT-6.2 Sol campaign: eight graded, eight context-blocked. Recorded conditional mean F1 0.875. Seven disclosed scores recomputed, one parser failure withheld.
- Deterministic BFS reference control: all 200 tasks F1 1.0, zero model calls.

The original experiment archives are retained in Git. No publisher aggregate is reproduced, and provider origin, full-answer extraction and invoice accuracy are not independently authenticated. See [campaign evidence](OPENAI_CAMPAIGN.md) and [methodology](METHODOLOGY.md).

## Installation and validation

Install from the repository with Python 3.10+ and Git; run `claim-replay demo`. The demonstration is synthetic. The [development guide](DEVELOPMENT.md) describes cross-platform package validation, advisory checks and production browser verification. See [usage](USAGE.md) for supported commands.

## Known limits

The narrow Inspect importer does not support arbitrary evaluators; private Chartography access and publisher protocols remain unresolved. External developer and score review have not been completed. The release must not be represented as validated by independent users until that evidence is recorded.

Before creating a tag, record the exact approved revision, successful CI and production runs, package hashes, and remaining release-gate decisions. Publish only the reviewed artifacts. Do not trigger any paid experiment in a release workflow.
