# Methodology and evidence standard

Model Claim Replay measures whether a *specific published numerical statement* can be independently examined under the relevant protocol. It does not assume a headline score is replicable from a few API calls.

## Claims and protocols

A claim manifest records its publisher, exact source URL, model label, published value, benchmark identity, task count, scoring protocol, and known blockers. Published metrics need a verified original statement. A missing benchmark digest is a hard stop in the portable executor. Official third-party harnesses remain external; their invocation and output schema must be validated before an adapter is implemented.

Portable task files are exact bytes of UTF-8 JSONL with one `id`, `prompt` and `expected` per task. The manifest specifies SHA-256 of the entire file, task count and normalization. Exact match is an intentionally narrow metric. The CLI does not silently coerce it into model-graded correctness or a judge-derived score.

## Statistical interpretation

For binary task outcomes with `s` successes among `n` graded tasks, accuracy is `s/n`. A two-sided 95% Wilson score interval is reported solely as a conventional descriptive uncertainty bound under independent Bernoulli trials. The assumption is inappropriate for correlated examples, repeated epochs, adaptive prompt selection, judge noise and nonrepresentative subsets. Such cases need cluster-aware or hierarchical inference and explicit protocol-specific methods. Errors are separately counted and excluded from the graded denominator; missing coverage prevents a comparable conclusion.

Published and observed scores are **not** subjected to a generic significance test. Many published figures depend on multiple epochs, private task samples, uncertain sampling designs or undisclosed graders. Comparing two isolated percentages is insufficient evidence of a statistically meaningful improvement or disagreement.

## Evidence hierarchy

1. **Source registered** — published statement and metadata, no execution evidence.
2. **Protocol mapped** — original harness, settings, data access, scoring and rights documented.
3. **Local self-reported attempt** — locally generated artifacts bound by hashes, with task-level records.
4. **Independent rerun** — an external party executes the declared protocol with its own provider access and publishes traceable results.
5. **Audited reproduction** — source data, harness, model identity, judge, execution environment and statistics satisfy an externally reviewed evidence standard.

The current CLI implements the local attempt and verification portions for a portable exact-match subset. Even a `candidate_protocol_match_self_reported` result is not classified as externally audited.

## Integrity and trust

The run metadata commits to the bytes of the claim manifest, task dataset, and JSONL responses. SHA-256 detects subsequent mutation if the metadata is held fixed. A malicious actor can replace both the data and its digest. There is no signature, protected log, identity attestation or tamper-resistant trace in v0.1. Never call a verified bundle proof of authentic provider execution.

Model aliases and hosted APIs are mutable. The portable adapter records the requested model label and raw textual responses, not server-side weights or an immutable model build. Judge models, adjudication rubrics, task exclusions, contamination, prompt formats, repeated sampling, maximum token settings, failure handling, costs and license terms all require individual review.

## Publication rule

Do not publish a discrepancy headline without the complete declared population or a predeclared defensible sampling design, a matched evaluator, coverage accounting, raw outputs, source citations and appropriate uncertainty. Label every synthetic test and partial run. If reproduction is blocked, publish the blocker as a blocker, never as evidence of failure by the model provider.
