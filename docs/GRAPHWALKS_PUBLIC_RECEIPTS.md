# Verify redacted GraphWalks public receipts

## Purpose

A successfully completed, manually authorized GraphWalks diagnostic uploads four redacted JSON artifacts. Three are the inputs to the independent consistency verifier:

- `token-plan.json`: model identity, public candidate source digest, selected task IDs, provider-reported input token counts and worst-case cost reservations, with no raw prompts or answers.
- `pilot-audit.json`: local journal consistency checks, intent/result hashes and per-task statuses, with no raw model responses.
- `pilot-scores.json`: the offline scorer's task-level F1, parser failures and coverage, with no gold answers or raw model responses.

The fourth file, `pilot-public-verification.json`, records the verifier's independent consistency verdict and the hashes of the three supplied inputs. A fifth artifact, `pilot-public-report.html`, is a standalone human-readable view of the same verified receipts. The workflow publishes task-level grades only after this verification succeeds. A failed or interrupted paid step can yield a **plan and audit only**, preserving unresolved request statuses while withholding an unverified score report.

A reader should be able to ask whether these three artifacts describe the **same** experiment without having to reconstruct a private journal. The dependency-free command `verify-graphwalks-public` performs exactly that cross-check.

## Usage

Download the plan, audit and grades from a fully completed, manually authorized diagnostic workflow, then rerun the verification independently:

```bash
python -m pip install -e .
claim-replay verify-graphwalks-public \
  --plan token-plan.json \
  --audit pilot-audit.json \
  --grades pilot-scores.json \
  --out verification.json
```

For a standalone, shareable HTML inspection report, run the same receipt checks with:

```bash
claim-replay report-graphwalks-public \
  --plan token-plan.json \
  --audit pilot-audit.json \
  --grades pilot-scores.json \
  --out graphwalks-evidence.html
```

Open `graphwalks-evidence.html` locally. The report displays all 200 task identities, individual journal and scoring states, F1 for graded tasks, source commitments, and the distinction between a scored subset and the complete benchmark. You can filter the table by declared pilot, graded rows, and unresolved or errored attempts. A Google-reported 95.2% figure appears separately as **publisher context, not a comparison**. The generator refuses inconsistent receipts or existing output and rehashes each source artifact before rendering. The HTML includes no prompt text, answer-node lists, raw model responses, external scripts, or tracking.

No network request, provider credential, original 297 MB source Parquet, reference answer index, or external Python dependency is used. The verifier refuses to overwrite an existing output file. A nonzero exit status indicates malformed or inconsistent receipts. The resulting JSON contains the SHA-256 of each exact input file for later identification.

## Checks actually performed

The verifier binds the audit's plan digest to the **exact** supplied token-plan file and compares source/index commitments with the locally pinned public candidate dataset metadata. It validates unique planned IDs, task-level pricing arithmetic, context feasibility, total reserved USD, attempted and completed counts, and the audited per-task statuses.

It then matches each of the public scorer's 200 task IDs to the audited attempts. An audited completed request must appear as graded; a recorded error must appear as an error; unresolved requests and tasks never attempted must remain missing. Unplanned task IDs cannot acquire a score. Counts of graded, malformed, parsed, missing and failed tasks are recomputed from the scored rows. For graded tasks, the reported F1 is checked against the reported precision and recall, and the subset mean is recalculated. A full-cohort mean is refused unless all 200 tasks have graded results.

The verifier also refuses any report that upgrades a self-reported diagnostic to publisher-comparable or independently authenticated evidence.

## What passing does not establish

This is an **internal-consistency check**, not a cryptographic proof of the model's execution or the accuracy of its answers. The three public files do not expose the model responses, gold answer lists, raw prompts, provider-side request logs or provider invoices. The verifier cannot recompute recall against the gold references, validate the actual prompt delivery, authenticate the model, or prove the declared source revision was actually executed.

In particular, an actor who controls all three receipts can fabricate a mutually consistent set. Local SHA-256 digests detect changes relative to a separately trusted digest; their mere presence does not authenticate authorship or execution. The tool does not infer missing response texts or score unresolved requests as incorrect. It also cannot establish that Google's reported cohort or protocol equals the available public candidate.

The validated output consequently uses:

```json
{
  "verification_status": "internally_consistent_self_reported_only",
  "claim_reproduced": false,
  "provider_execution_authenticated": false,
  "score_recomputed_from_model_outputs": false,
  "source_dataset_reverified": false,
  "comparison_status": "not_comparable"
}
```

These fields are fixed by the verifier; they do not depend on a provided self-declaration.

## Independent test strategy

`tests/test_graphwalks_public.py` creates small synthetic receipt metadata and a 200-row score index, then tests legitimate partial coverage, changed token-plan bytes, forged completed requests, invalid F1 and means, duplicate or unplanned task IDs, incorrect reserved budgets, NaN values and unresolved attempts. These tests make no paid API calls and do not stand in for the first real GraphWalks model observation.

The [GraphWalks execution guide](GRAPHWALKS_EXECUTION.md) describes the separate provider protocol, authorization gates and original task-level scoring.
