# Model Claim Replay

### They published the score. Show the experiment.

**Published AI benchmark results deserve independently inspectable evidence.** Model Claim Replay is an open-source project to turn individual model-launch claims into reproducible experiments, with pinned inputs, declared execution protocols, independently rerunnable scoring, uncertainty, and shareable reports.

## Run your first evidence replay

Python 3.10+; no model key, paid inference, or third-party runtime packages. Install directly from GitHub and generate a **fully offline synthetic** evidence bundle from any directory:

```bash
python -m pip install "git+https://github.com/fraware/model-claim-replay.git"
claim-replay demo
```

Open `.runs/demo/report.html` in a browser. The bundled three-task exercise imports fixed responses, recomputes exact-match scores, checks SHA-256 integrity, and creates independent HTML/JSON reports. Its **2/3 score is synthetic** and cannot be used to support any published model claim. Run `claim-replay demo --out another-directory` to create a second exercise; the command never overwrites an existing bundle.

[Live website](https://fraware.github.io/model-claim-replay/) · [Explore 200 verified GraphWalks tasks](https://fraware.github.io/model-claim-replay/graphwalks.html) · [Download the input-feasibility figure](website/graphwalks-input-feasibility.svg) · [Website source](website/) · [Methodology](docs/METHODOLOGY.md) · [Chartography research](docs/CHARTOGRAPHY.md) · [GraphWalks research](docs/GRAPHWALKS.md) · [Roadmap](docs/ROADMAP.md) · [Contribute](CONTRIBUTING.md)

> **Project status — foundation, not a completed benchmark replication.** The CLI executes pinned *portable text* fixtures, imports scored Inspect AI logs from an official evaluation, verifies local evidence hashes, compares compatible runs on identical task/epoch pairs, and generates standalone HTML/JSON reports. The registered Chartography and Gemini 4 Neon / GraphWalks claims are real published statements, **not** completed reproductions. Dataset access, licensing, model settings, judge protocol, and budget still need to be resolved before real comparison is justified. No provider result is invented.

**Live interactive website:** [fraware.github.io/model-claim-replay](https://fraware.github.io/model-claim-replay/), published automatically from `website/` through GitHub Pages. The web demonstrations use fixed synthetic data; real evaluation and report generation run locally.

**Help validate the first release:** try the offline CLI, then [report your experience](https://github.com/fraware/model-claim-replay/issues/new?template=developer-replay-feedback.yml), including unsuccessful attempts. [Release criteria and test protocol](docs/RELEASE_ACCEPTANCE.md).

## Check your bundle in a browser

[Open the local evidence checker](https://fraware.github.io/model-claim-replay/check.html). Select the original run manifest, claim manifest and results file; portable-text bundles also require the original task data. Inspect bundles support an optional original log check. The browser compares SHA-256 commitments locally with no file upload. It does not authenticate execution, validate the full schema or recompute scores. Use `claim-replay verify` for full CLI validation.

## The ambition

A public claim should lead to a public experiment. We aim to make the following routine for any significant model launch:

1. **Select the claim.** Link to an exact, dated publisher statement, metric, benchmark, model, and evaluation setting.
2. **Inspect what is known.** Distinguish available task data, proprietary tests, official harnesses, judges, model aliases, and unresolved conditions.
3. **Run the original evaluation.** Integrate with the benchmark's *official* harness where one exists. Never substitute a convenient proxy without explicit disclosure.
4. **Examine every result.** Record model outputs, scoring decisions, errors, task coverage, compute and API usage, artifact hashes, and uncertainty.
5. **Publish a defensible report.** Say precisely what was reproduced, what differed, what remains untestable, and how others can rerun the experiment.

The long-term product is a **living, versioned claim registry** plus reproducible evaluation recipes and shareable evidence reports. We do not intend to replace Inspect AI, NeMo Evaluator, or Promptfoo. Those are execution engines; Model Claim Replay is the source-to-evidence workflow around an individual public claim.

## Published claims under investigation

- **Claude Fable 5.2 / Chartography — 73.4% reported.** Official harness and an Inspect AI importer are operational; the complete private evaluation population and exact publisher conditions are unresolved. [Reproduction dossier](docs/CHARTOGRAPHY.md).
- **Gemini 4 Neon / GraphWalks BFS — 95.2% F1 reported.** The 200-problem long-context result was published 18 November 2026. The [original dataset](https://huggingface.co/datasets/openai/graphwalks) is public under MIT, but the candidate long-context Parquet was independently SHA-256 verified, contains exactly 200 BFS tasks, and its published grader is implemented locally. Google's own data revision, task selection, API settings and substantial inference costs remain unresolved. [Feasibility dossier](docs/GRAPHWALKS.md).

**First live GraphWalks feasibility observation (23 November 2026).** An [authenticated Gemini token-count run](https://github.com/fraware/model-claim-replay/actions/runs/45156733056) against two original, SHA-256-verified public BFS prompts reported **355,124** input tokens for the short-context candidate and **1,419,783** for the long-context candidate. The latter exceeds the runner's declared **1,048,576-token** context limit even with zero output tokens. It is a context-feasibility finding for this particular public candidate, **not** a generated model answer or a reproduction of Google's unpublished 200-task selection. A [20-task follow-up](https://github.com/fraware/model-claim-replay/actions/runs/45158739147) found **10/10 shorter tasks fitting** and **10/10 longer tasks exceeding** the provider-reported input limit; a [complete authenticated 200-task scan](https://github.com/fraware/model-claim-replay/actions/runs/45159511810) confirmed **100/100 shorter inputs fit and 100/100 longer inputs exceed the provider-reported input limit**. The full result and all 200 source-bound token counts are available in the [interactive public explorer](https://fraware.github.io/model-claim-replay/graphwalks.html). [Permanent original token receipt](evidence/graphwalks/gemini-4-neon-two-task-token-plan-2026-11-23.json) · [Execution dossier](docs/GRAPHWALKS_EXECUTION.md).

Neither headline has been independently reproduced. [Our byte-verified 200-task BFS index](https://github.com/fraware/model-claim-replay/actions/runs/44746523023) is available as a reproducible CI artifact. The GraphWalks scorer is distinct from the Chartography Inspect importer. Neither component authenticates the model provider.

## OpenAI default provider

The generic CLI already uses the OpenAI endpoint. The protected-main readiness workflow now checks the exact `gpt-6.2-sol` model using `OPENAI_API_KEY` or `OPENAI_KEY`; it never probes Gemini or substitutes another provider. Metadata access is not proof of inference readiness.

The [OpenAI GraphWalks diagnostic workflow](https://github.com/fraware/model-claim-replay/actions/workflows/graphwalks-openai-paid.yml) is a separate, single-task Responses API experiment on pinned public candidate task `bfs-row-000100`, at `xhigh` reasoning and 65,536 output tokens. In a new main-branch dispatch, the default `PREFLIGHT_ONLY` option measures input tokens and estimates the reservation, with no generation or spending authorization. To run the paid diagnostic, explicitly select `AUTHORIZE_PAID_OPENAI` from the approval dropdown and choose a ceiling (default $5). It obtains fresh OpenAI token counts, uses conservative standard long-context rates (including a 30-minute cache-write allowance, with implicit caching disabled), refuses infeasible or over-budget input, writes a durable intent, and never retries a billable generation. Full provider responses and reasoning are never uploaded. The separate publication dropdown defaults to `REDACTED_ONLY`. Selecting `PUBLISH_FINAL_LINE` in paid mode authorizes public disclosure of the exact canonical GraphWalks final answer line (or an empty final line); noncanonical text is withheld. This allows offline score recomputation from the disclosed line while extraction fidelity to the full response remains unattested. The result is not a reproduction of Google's Gemini claim. That historical investigation remains separate.

The [automatic source-bound OpenAI preflight](.github/workflows/graphwalks-openai-preflight.yml) runs only when its own workflow changes on `main`. It verifies the original dataset and calls the metadata and input-token endpoints through a separate endpoint allowlist. Its $5 planning ceiling is hypothetical; it never authorizes or invokes generation, and only the score-free plan and outcome are retained. A successful preflight is not a model score.

**Live result:** GPT-6.2 Sol counted 255,598 input tokens on the original pinned candidate `bfs-row-000100`. The estimated maximum generation reservation is $2.26103 under the declared conservative rate table. The [original run](https://github.com/fraware/model-claim-replay/actions/runs/45337852354) and [public log-derived summary](website/graphwalks-openai-preflight.json) retain the evidence. No generation, actual charge or model score is asserted.

After a paid run with a published final line, download the diagnostic artifact and obtain the independently generated pinned BFS reference index from the [source audit](https://github.com/fraware/model-claim-replay/actions/runs/44746523023). Verify the score offline:

```bash
python -m model_claim_replay.openai_graphwalks_verify \
  --bundle /path/to/extracted/diagnostic \
  --index /path/to/graphwalks-bfs-reference-index.jsonl
```

Use the directory containing `plan.json`, `intent.json`, `outcome.json` and `scoring-evidence.json`. Verification checks the reference-index hash, source task and prompt commitments, receipt digests and exact F1. It neither authenticates the provider response nor proves that the disclosed line was faithfully extracted from the full answer. External independent rescoring is still required.

### First-generation pilot

**Live generation completed:** GPT-6.2 Sol recovered all 9 reference nodes on the prespecified public BFS task `bfs-row-000100`. F1, precision and recall = 1.0 for the disclosed final answer line. The API reported 255,598 input tokens and 572 output tokens; the conservative usage-based estimate is $1.28943 (not an invoice). The workflow verifier and a separate offline recomputation agree. [Original Actions run](https://github.com/fraware/model-claim-replay/actions/runs/45398852989) · [Original byte-identical archive](evidence/graphwalks/openai-first-generation-2026-11-24/original-actions-artifact.zip) · [Recompute the score](evidence/graphwalks/openai-first-generation-2026-11-24/README.md) · [Prespecified 16-task follow-up](https://github.com/fraware/model-claim-replay/issues/42). Single-task diagnostic, no publisher reproduction or external third-party verification.


The [one-time authorization record](evidence/graphwalks/openai-first-generation-authorization.json) permits one GPT-6.2 Sol generation on the already measured source task with a $5 reservation ceiling and restricted final-line publication. Its dedicated main-push workflow checks the exact record, first introduction in Git history, and initial run attempt before obtaining credentials. No recurring paid trigger, automatic retry, or reusable authorization is introduced. Future runs use the manual workflow. The reservation is an estimate, not a provider-enforced account spending cap. New runs reserve $20/M output as an extra margin above the documented $15/M long-context Standard rate. The earlier preflight's $2.26103 remains its original recorded estimate; at the revised rates the same measured input reserves $2.58871. The one-time run completed successfully on 24 November 2026 UTC.

## Score GraphWalks responses offline

A dedicated `grade-graphwalks` CLI command follows the published GraphWalks final-line answer parser and node-set F1. It checks the supplied BFS reference-index SHA-256 and scores recorded model outputs **without making API calls**. Original dataset rows and prompt input fidelity still need separate verification, and the resulting report is never labeled a publisher reproduction.

```bash
claim-replay grade-graphwalks \
  --index examples/graphwalks-demo-index.jsonl \
  --responses examples/graphwalks-demo-responses.jsonl \
  --index-sha256 b39f93f5828a11ba43a72bcd0e456a93933ef8a8155d206e19053b89801b57b4 \
  --dataset-revision 0000000000000000000000000000000000000000 \
  --out .runs/graphwalks-synthetic.json
```

Both records and the revision marker above are **synthetic**. The 5/6 F1 is a fixture result, not a model evaluation. For a real source-index format, correct score semantics and the pinned HF metadata snapshot, see [the GraphWalks dossier](docs/GRAPHWALKS.md).

## Explore the verified GraphWalks source data

The [interactive 200-task GraphWalks audit](https://fraware.github.io/model-claim-replay/graphwalks.html) visualizes the complete SHA-256-verified candidate BFS cohort. Explore source row identities, input sizes and task-level prompt commitments without downloading the original large dataset, revealing raw benchmark prompts, or confusing publisher-reported performance with independent testing. The source-explorer JSON is reproducibly generated from the pinned 200-task reference index by `scripts/publish_graphwalks_summary.py`. Its separate [provider count receipt](website/graphwalks-gemini-feasibility.json) contains all 200 measured token counts in that index order and identifies the byte-identical [original GitHub Actions token plan](evidence/graphwalks/gemini-4-neon-full-200-token-plan-2026-11-23.json) by SHA-256; no prompts, answers, or generated completions are published.

## First complete public-data control — 200/200 tasks

Our [source-bound deterministic BFS control](docs/GRAPHWALKS_CONTROL.md) executed against all **200 independently SHA-256-verified public GraphWalks BFS tasks**, achieving **F1 1.0 on all 200** under the original benchmark grader. The audit recorded zero parser failures and exactly 100 tasks in each source-length cohort. The [official GitHub Actions run](https://github.com/fraware/model-claim-replay/actions/runs/44884895995) and [task-level receipt](website/graphwalks-control.json) are public.

**Interpretation:** this is a specialized algorithm reading graph edges from prompts, **not Gemini inference** or a comparison to the published model's 95.2%. It demonstrates internal agreement of the public prompts, graph traversal and source reference answers. The separate model claim remains independently untested.

## Model-free algorithmic control

A [reproducible deterministic BFS control](docs/GRAPHWALKS_CONTROL.md) independently parses the original public graph prompts and runs graph traversal **without any model API calls**. A dedicated [GitHub Actions workflow](https://github.com/fraware/model-claim-replay/actions/workflows/graphwalks-algorithmic-control.yml) verifies the entire source file and scores this algorithm against all 200 pinned BFS answers. It publishes per-task parsing and F1 evidence without raw graph prompts or answer lists. This is a structural control to test the dataset and scorer, **not** a reproduction of Gemini's reported score. The project explicitly acknowledges [FalkorDB's existing graph/LLM proxy](https://github.com/FalkorDB/GraphWalks) as related prior work.

## Run an explicitly authorized Gemini diagnostic

A [manual GitHub diagnostic workflow](https://github.com/fraware/model-claim-replay/actions/workflows/graphwalks-paid-pilot.yml) now connects the pinned public GraphWalks dataset to actual Gemini token counting, controlled generation, the private journal audit, and the original offline F1 scorer. **No Gemini generation experiment has been run.** The workflow has no push or scheduled trigger: its default approval is `NO`, its default budget is `0`, and generation is blocked unless the maintainer types `AUTHORIZE_PAID_GEMINI` and sets a positive USD ceiling of at most $100. A full selected-cohort cost reservation must fit the approved ceiling.

The default **one-task pilot** selects a short-context BFS prompt. The two-task selection includes a long-context prompt already shown to exceed the provider-reported limit; the full-cohort gate blocks generation in that case. GitHub job reruns are rejected before checkout: review prior evidence and potential charges, then initiate a fresh manual dispatch with a new explicit spending approval. GitHub uploads only the no-prompt token plan, redacted self-reported journal audit, and, after a successful cross-receipt consistency check, task-level grades and a verification receipt. After an interrupted paid step, the redacted audit is still attempted and scored artifacts are withheld. It never uploads prompts, gold answers, or raw model responses. One working repository Gemini Actions secret (`GEMINI_API_KEY`, `GOOGLE_API_KEY` or `GOOGLE_GENAI_API_KEY`) is necessary. Both manual workflows authenticate the pinned model before downloading data and inject only the selected credential into provider-facing execution steps. This is a *diagnostic*, not a verified reproduction of Google's 95.2%; the provider protocol and publisher cohort remain unresolved. Read the [execution and budget guide](docs/GRAPHWALKS_EXECUTION.md) before authorizing any spending.

## Verify and inspect a public GraphWalks diagnostic

When a real authorized diagnostic publishes a complete set of redacted artifacts, any developer can download its token plan, journal audit, and task-level grades, check them offline and generate a self-contained HTML report. The published fourth receipt records the workflow's own cross-check. An interrupted run may publish only the plan and audit, with no scoring artifact. No Gemini credential, source Parquet, answer index, model response text, or external dependency is necessary.

```bash
claim-replay verify-graphwalks-public \
  --plan token-plan.json \
  --audit pilot-audit.json \
  --grades pilot-scores.json \
  --out verification.json
```

To explore the same redacted evidence in a browser, run:

```bash
claim-replay report-graphwalks-public \
  --plan token-plan.json \
  --audit pilot-audit.json \
  --grades pilot-scores.json \
  --out graphwalks-evidence.html
```

The HTML enumerates 200 task identities with explicit states, per-task scores and input hashes. It never includes private prompts, reference answers or raw model responses. Scored-subset F1 and the publisher's headline are labeled separately.

This command checks the cross-artifact plan digest, pinned candidate source identities, task-status correspondence, missing trials, cost reservations, score arithmetic and denominator accounting. **A passing result establishes internal consistency of self-reported redacted evidence only.** It does not recalculate F1 from private model outputs or authenticate Google, the original source bytes, the benchmark judge, or invoice charges. See the [public-receipt verification contract](docs/GRAPHWALKS_PUBLIC_RECEIPTS.md) for the exact guarantees and limits. No paid pilot receipts have been released as of 21 November 2026.

## Run GraphWalks with explicit token and spending gates

The next research milestone is implemented as a **two-stage Gemini 4 Neon execution adapter**. `claim-replay plan-graphwalks` verifies the entire 200-task public source and calls Google's token-count endpoint without generating model answers; `claim-replay execute-graphwalks` only sends billable requests after an explicit `--execute-paid` authorization and an independently checked maximum budget reservation. It writes durable attempt intents before each request and uses a fixed-endpoint one-POST REST transport for paid inference, with no SDK-managed retry or continuation. `claim-replay audit-graphwalks` verifies task intents, provider-response metadata, local hashes and budget reservations without publishing response text. `claim-replay export-graphwalks` now requires the pinned reference index and a passing journal audit before exporting private answers for the original F1 scorer.

The adapter is candidate-dataset research infrastructure, **not** reproduction of Google's reported 95.2%. No Gemini inference has been performed on this project's behalf. Exact publisher settings, actual model usage, and the full authorized experiment remain outstanding. A [manual GitHub token-count preflight](https://github.com/fraware/model-claim-replay/actions/workflows/graphwalks-token-preflight.yml) is available for maintainers with any supported Gemini Actions secret. Its prespecified multi-task selection covers both the 256K-class and 1M-class public source cohorts; a 20-task diagnostic comprises 10 from each group. It independently verifies source bytes and publishes only a non-generative, score-free token and cost plan. For commands, source SHA-256, token limits, pricing assumptions and error semantics, read the [GraphWalks execution guide](docs/GRAPHWALKS_EXECUTION.md).

## Try it now — fully offline

Python 3.10+; no runtime dependencies and no API key needed for the bundled demonstration.

```bash
git clone https://github.com/fraware/model-claim-replay.git
cd model-claim-replay
python -m pip install -e .
claim-replay list
claim-replay inspect claims/claude-fable-5-2-chartography.json
claim-replay evaluate \
  --claim claims/demo-text-exact-match.json \
  --tasks examples/demo-tasks.jsonl \
  --responses examples/demo-responses.jsonl \
  --model fixture-model --out .runs/demo
claim-replay verify .runs/demo \
  --claim claims/demo-text-exact-match.json --tasks examples/demo-tasks.jsonl
claim-replay report .runs/demo \
  --claim claims/demo-text-exact-match.json --tasks examples/demo-tasks.jsonl \
  --format html --output .runs/demo.html
```

Open `.runs/demo.html` in any browser. The **2/3 score is synthetic**, and the output is explicitly marked self-reported. The report never presents the fixture as independent evidence of a real model's performance.

## Import an official Inspect AI evaluation log

The new `import-inspect` command uses [Inspect's public Log API](https://inspect.aisi.org.uk/eval-logs.html) to read `.eval` or `.json` benchmark logs. Only a narrow Chartography score importer is implemented at present. The original benchmark scorer is **never replaced**, and no full dataset content is bundled.

```bash
python -m pip install -e '.[inspect]'
claim-replay import-inspect \
  --claim claims/claude-fable-5-2-chartography.json \
  --log /path/to/official-run.eval --out .runs/chartography
claim-replay verify .runs/chartography \
  --claim claims/claude-fable-5-2-chartography.json \
  --source-log /path/to/official-run.eval
claim-replay report .runs/chartography \
  --claim claims/claude-fable-5-2-chartography.json \
  --output .runs/chartography.html
```

The official-upstream CI smoke check runs the **real Chartography harness** on its two dummy tasks with mock generation and mock judging, preserving unscored results without reporting model accuracy. It never calls a paid model or evaluates the private 100-task benchmark. Successful [GitHub CI runs](https://github.com/fraware/model-claim-replay/actions/workflows/ci.yml) now retain a 14-day downloadable score-only artifact with an offline report; original Inspect logs and task content are excluded.

The importer rejects corrupted score types, duplicate task/epoch records, inconsistent original aggregate scores for complete reference grids, and incompatible task identities. It reports precise coverage and preserves *pseudonymous* task-level scores, source log SHA-256, recorded judge/dataset/model metadata and unresolved protocol differences. It does not export private charts, prompts, gold answers, raw responses or judge rationales. **A successful import is not an independent reproduction.** See the [Chartography reproduction dossier](docs/CHARTOGRAPHY.md) for upstream code revision, access constraints and full evaluation protocol.

### Compare two original Inspect run logs

Import each model's **actual Inspect log** against the same claim manifest, using separate output directories, and compare them without assuming that the publisher's headline was reproduced.

```bash
claim-replay import-inspect \
  --claim claims/claude-fable-5-2-chartography.json \
  --log /private/path/first.eval --out .runs/model-a
claim-replay import-inspect \
  --claim claims/claude-fable-5-2-chartography.json \
  --log /private/path/second.eval --out .runs/model-b
claim-replay compare-inspect \
  --claim claims/claude-fable-5-2-chartography.json \
  --left .runs/model-a --right .runs/model-b \
  --format html --output .runs/paired-report.html
```

The paired audit refuses mismatched task/epoch sets, missing or irregular repeats, unscored samples, unverified harness revisions and missing or conflicting recorded judge/dataset settings. For compatible imports it reports the **right-minus-left difference in percentage points** and an exploratory *task-cluster bootstrap interval*, preserving repeated trials within each task. An observed paired difference is explicitly **diagnostic, self-reported, and conditional on the selected tasks**; it never certifies that Anthropic's 73.4% was reproduced. The supplied log digests are recorded, and the original task images and responses stay local. If one run had missing scores or mismatched inputs, the comparison is blocked instead of dropping those observations.

### Call a real model using the portable runner

For a claim with a pinned *text-only exact-match* dataset and compatible declared conditions:

```bash
export OPENAI_API_KEY="..."
claim-replay run \
  --claim claims/demo-text-exact-match.json --tasks examples/demo-tasks.jsonl \
  --model <your-model-id> --base-url https://api.openai.com/v1 \
  --limit 3 --out .runs/local-model
```

This demonstration tests the adapter and fixture, **not** Chartography or any vendor headline. The adapter speaks OpenAI-compatible chat-completions; providers differ in supported parameters and token accounting. It does not implement official third-party evaluators. Each request is performed once, without redirect following or automatic retries; responses stopped by length limits, content filtering or tool handoffs are not silently graded as completed answers. API fees are the user's responsibility. Local secrets are read from an environment variable, not written into artifacts. Only explicit loopback `http://` endpoints are supported; remote endpoints must use HTTPS.

## What the evidence means

| Report field | Interpretation |
|---|---|
| Publisher-reported result | A sourced claim, never inferred from a local score |
| Observed result | Exact-match score recomputed against pinned tasks |
| Task accounting | Passed, failed, API errors, total and attempted counts |
| 95% Wilson interval | Descriptive only under i.i.d. Bernoulli assumptions; may be inappropriate for correlated tasks |
| Content SHA-256 | Detects accidental artifact changes, **not** fraudulent or unauthenticated runs |
| Comparison status | `not_comparable` for published claims without authenticated protocol equivalence; Inspect pairs receive `paired_diagnostic_only` or `blocked` |

See [the methodology](docs/METHODOLOGY.md) for limitations, publication standards, trust boundaries and why a subset is never represented as a full reproduction.

## First external claim under investigation

Anthropic's **Claude Fable 5.2 / Chartography (no tools)** figure of **73.4%** is recorded at [`claims/claude-fable-5-2-chartography.json`](claims/claude-fable-5-2-chartography.json), anchored to [Anthropic's November 2026 announcement](https://www.anthropic.com/claude-fable-and-mythos-5-2) and [the official Chartography implementation](https://github.com/surge-ai/chartography). The claim remains **blocked for reproduction** until dataset licensing/access, scoring/judge settings, repeat protocol and an appropriate inference budget are validated. We will favor the official Inspect AI runner, not reimplement the benchmark superficially.

## Principles

- **Evidence before narrative.** A discrepancy is meaningful only with a defensible experiment.
- **No claim laundering.** A synthetic example, partial run, modified prompt, missing judge, or new model snapshot must be labeled as such.
- **Portable by design.** Published manifests and reports are JSON and static HTML; no account, telemetry, hosted database, or vendor lock-in.
- **Reproducibility is scoped.** Third-party API responses and mutable endpoints are not automatically verifiable. Hashes are not execution attestations.
- **Open contribution.** New claims are admitted through documented source and protocol checks.

## Development

```bash
python -m unittest discover -s tests -v
python -m pip install -e .
```

### Test the interactive website

The static site includes two interactive, explicitly synthetic demonstrations: task-level score replay and a paired-run protocol gate (matched settings, changed judge, missing trial). Run browser-level desktop/mobile regression tests without publishing a site or calling an API:

```bash
python -m pip install playwright
python -m playwright install chromium
python scripts/visual_smoke.py --output-dir .runs/previews
```

This optional test covers interactive states, accessible button states, JavaScript exceptions and horizontal layout overflow. It does not assert that GitHub Pages is active or that a published claim has been reproduced.

MIT-licensed source. **External benchmark datasets, models and evaluator implementations retain their original owners' terms** and are not redistributed by this repository.
