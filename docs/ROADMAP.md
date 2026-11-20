# Roadmap: ambitious destination, evidence-led milestones

## Milestone 0 — Operational foundation (implemented and tested)
- Open, source-anchored claim manifests and explicit blocked status.
- Dependency-free Python CLI for portable text tasks and external response import.
- SHA-256-bound local evidence bundles, task accounting, scoring and standalone HTML/JSON reports.
- Automated tests and GitHub Actions CI, plus a deployed static website with interactive synthetic demonstrations, and desktop/mobile browser smoke checks.

## Milestone 1 — First independent claim reproduction (in progress)
- Verify rights and access for an important, developer-relevant published benchmark.
- Pin an official harness revision, task IDs, judge settings, model API parameters and budgets.
- **Implemented:** Import official Inspect AI `.eval`/`.json` logs with task/epoch validation and no scorer replacement, tested against Inspect's real mock-model runtime.
- **Implemented:** Score-only paired diagnostics for separate Inspect logs with exact task/epoch matching, protocol checks and task-level bootstrap resampling. This is *not* a reproduction or an authenticated provider comparison.
- **Pending:** Establish access and match the exact publisher protocol before making any reproduction claim.
- Collect raw task-level outputs and independently check all scoring and uncertainty calculations.
- Publish evidence and limitations, including negative findings and inconclusive outcomes.

## Milestone 2 — Contributor-grade claim registry (planned)
- Manifest schema validation and provenance review workflow.
- First-class adapters to Inspect AI and other official harness formats, not duplicate harness implementations.
- Dataset manifests and provenance checks, licensing gates and reproducible environment locks.
- Public claim pages generated from signed release artifacts, with explicit status transitions.

## Milestone 3 — A model-launch companion (planned)
- Timely model announcement ingestion and human-reviewed claim selection.
- One-command benchmark reproduction where data, permissions, cost and protocols permit it.
- Extend initial paired-score diagnostic to task-level disagreement inspection with permission-aware artifact access, calibrated uncertainty and actual runtime costs.
- Community reruns with independent identities, reproducibility scoring and immutable evidence releases.

## Product standard

We will optimize for independent usefulness and extraordinary execution quality. Timed launches are an amplification strategy, not a justification for speculative benchmarks. Top GitHub Trending Daily is an aspiration, not an experimental finding or a metric we can promise.
