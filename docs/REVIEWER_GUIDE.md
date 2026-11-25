# Independent reviewer guide

[Documentation home](README.md) · [Release acceptance](RELEASE_ACCEPTANCE.md)

This guide supports two distinct activities: evaluating the installation experience and checking the historical research evidence. Participation is voluntary. Report unsuccessful attempts and disagreements. The project does not request stars, endorsements or model credentials.

## Start at a pinned revision

Use the full Git commit specified in your invitation. Install Python 3.10 or newer and Git. From a new directory:

```bash
git clone https://github.com/fraware/model-claim-replay.git
cd model-claim-replay
git checkout REVISION_FROM_INVITATION
python -m venv .venv
```

Activate with `source .venv/bin/activate` on POSIX or `.venv\Scripts\Activate.ps1` on PowerShell.

## Developer onboarding

Start timing when you open the quickstart. Include installation and opening the report in elapsed time. Use a fresh environment where feasible.

```bash
python -m pip install -e .
claim-replay demo --out .runs/reviewer-demo
```

Open `.runs/reviewer-demo/report.html`. Report what you observed before consulting the expected outcome. Inspect the [public GraphWalks finding](https://fraware.github.io/model-claim-replay/graphwalks.html) and explain what it establishes in your own words. If relevant, describe a specific task for which this tool would save time.

[Submit developer feedback](https://github.com/fraware/model-claim-replay/issues/new?template=developer-replay-feedback.yml). Record installation failures as well as successes. A non-attempt does not enter the completion denominator.

## Independent research review

After base-package installation, run:

```bash
python scripts/verify_archived_evidence.py
```

For an independent arithmetic check, examine the actual [source index archive](../evidence/graphwalks/REFERENCE_INDEX.md), [pilot archive](../evidence/graphwalks/openai-first-generation-2026-11-24/README.md) and [campaign archive](OPENAI_CAMPAIGN.md). Check file digests, compare task identities, form the distinct predicted and reference node sets from each disclosed final line, and recompute the node-set F1. Inspect the original parser convention for empty sets. Account for every selected campaign task. Treat withheld answers as inaccessible evidence; do not infer their contents.

[Submit independent evidence review](https://github.com/fraware/model-claim-replay/issues/new?template=independent-evidence-review.yml). State your relationship to the project and whether your score calculation was independent of its verifier. No unpublished full-answer authentication, invoice verification or publisher reproduction follows from these checks.

## Maintainer accounting

Use one record per independent participant per protocol. Record all attempted sessions, elapsed times, errors, revision, and specific use cases; exclude maintainer-run CI and simulated sessions from the external counts. Preserve corrections and failures. The release thresholds are specified in [release acceptance](RELEASE_ACCEPTANCE.md). A third-party review of disclosed final lines does not resolve the missing full-answer extraction evidence.
