# Methodology and evidence standard

Model Claim Replay measures whether a *specific published numerical statement* can be independently examined under the relevant protocol. It does not assume a headline score is replicable from a few API calls.

## Claims and protocols

A claim manifest records its publisher, exact source URL, model label, published value, benchmark identity, task count, scoring protocol, and known blockers. Published metrics need a verified original statement. A missing benchmark digest is a hard stop in the portable executor. Official third-party harnesses remain external. The Chartography adapter reads real Inspect AI logs through its documented Log API, preserves the upstream scorer’s output and recomputes binary task-epoch means; it does not implement the original judge.

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

## External benchmark evidence (`inspect-v1`)

An imported Inspect AI log uses a separate evidence schema from the portable exact-match runner. Import checks the successful evaluation status, `chartography` task identity, individual sample and epoch identity, binary `golden_answer_scorer` accuracy values, contradictory scorer metadata and duplicate task/epoch pairs. For a *complete, fully graded and balanced* task-epoch grid, its recomputed mean must equal the explicitly named original Inspect `accuracy/mean` aggregate (within `1e-8`). Incomplete and unscored runs retain explicit coverage accounting and never qualify as comparable.

For repeated evaluations, the reporter provides an exploratory *task-cluster* bootstrap only on a fully graded and complete grid, resampling the distinct tasks and averaging their epoch outcomes. Because the Chartography task set was curated, this interval is not a population-confidence guarantee or a test of a discrepancy against a publisher. Model/judge variability and selected task composition demand separate analysis.

The source log stays on disk. Only SHA-256 of the source log bytes, the manifest hash, scored outcomes, pseudonymous task identifiers and selected non-sensitive header metadata are exported. Task digests are pseudonyms, not anonymous identifiers secure against guessing. Importing a log, including a hash-verified log, remains **self-reported evidence**. An optional `--source-log` check verifies that the local original log still matches its recorded digest; it does not establish provider identity or judge correctness. The score exporter is purposefully not a replacement for retaining the original private log for an authorized audit.

Until the publisher's precise version, dataset revision, model identity, judge parameters, repeat protocol and rights conditions are documented and independently matched, the external report is always `not_comparable`. The published 73.4% figure is never overwritten by observed local values. See [CHARTOGRAPHY.md](CHARTOGRAPHY.md).

## Paired evidence comparison

Two logs for different model IDs are compared on exactly matching task pseudonyms and epoch numbers. The CLI refuses intersection-only score comparisons, incomplete trial grids, errors, missing verdicts, and any missing or conflicting provenance metadata used to establish protocol compatibility. The direction of the reported effect is **right minus left**, in percentage points. A task is resampled as the unit of the exploratory percentile bootstrap, preserving all its repeated epochs. This interval is conditional on the curated tasks and supplied log records, with no claim to a representative task population or independent execution. Identical source-log hashes are rejected as a tautological comparison. SHA-256 commitments detect modifications to local bytes; their existence does not authenticate the execution environment or the model provider. The reported result of a paired audit is `paired_diagnostic_only`, never confirmation or refutation of a source claim.

## Logged content consistency

Task-ID agreement and matching dataset repository names are insufficient for
paired evaluations. The importer now computes a deterministic SHA-256 commitment
over each sample's logged input, chart-image bytes and reference target. Images
are fingerprinted only if bytes are embedded as an inline base64 data URI.
Local file paths, remote URLs, missing images and unsupported content encodings
leave the content fingerprint unavailable. Those observations remain importable,
although paired scoring is blocked until content identity is established.
Inconsistent fingerprints across epochs of the same task are rejected.

**Scope of the guarantee:** matching fingerprints establish equality of the
*logged* input and reference content under this canonicalization. They do not
authenticate the model execution, prove the image was delivered to the model,
establish upstream dataset licensing, or establish parity with the publisher.
Digests are pseudonyms vulnerable to dictionary attacks on known examples.
No prompts, chart bytes or targets are exported in evidence bundles.
