# Model Claim Replay

### The model is 40% better. Let's reproduce that.

**Published AI benchmark results deserve independently inspectable evidence.** Model Claim Replay is an open-source project to turn individual model-launch claims into reproducible experiments, with pinned inputs, declared execution protocols, independently rerunnable scoring, uncertainty, and shareable reports.

[Live website](https://fraware.github.io/model-claim-replay/) · [Website source](website/) · [Methodology](docs/METHODOLOGY.md) · [Chartography research](docs/CHARTOGRAPHY.md) · [Roadmap](docs/ROADMAP.md) · [Contribute](CONTRIBUTING.md)

> **Project status — foundation, not a completed benchmark replication.** The CLI executes pinned *portable text* fixtures, imports scored Inspect AI logs from an official evaluation, verifies local evidence hashes, compares compatible runs on identical task/epoch pairs, and generates standalone HTML/JSON reports. The registered Chartography claim is a real published statement, **not** a completed reproduction. Dataset access, licensing, model settings, judge protocol, and budget still need to be resolved before real comparison is justified. No provider result is invented.

**Live interactive website:** [fraware.github.io/model-claim-replay](https://fraware.github.io/model-claim-replay/), published automatically from `website/` through GitHub Pages. The web demonstrations use fixed synthetic data; real evaluation and report generation run locally.

## The ambition

A public claim should lead to a public experiment. We aim to make the following routine for any significant model launch:

1. **Select the claim.** Link to an exact, dated publisher statement, metric, benchmark, model, and evaluation setting.
2. **Inspect what is known.** Distinguish available task data, proprietary tests, official harnesses, judges, model aliases, and unresolved conditions.
3. **Run the original evaluation.** Integrate with the benchmark's *official* harness where one exists. Never substitute a convenient proxy without explicit disclosure.
4. **Examine every result.** Record model outputs, scoring decisions, errors, task coverage, compute and API usage, artifact hashes, and uncertainty.
5. **Publish a defensible report.** Say precisely what was reproduced, what differed, what remains untestable, and how others can rerun the experiment.

The long-term product is a **living, versioned claim registry** plus reproducible evaluation recipes and shareable evidence reports. We do not intend to replace Inspect AI, NeMo Evaluator, or Promptfoo. Those are execution engines; Model Claim Replay is the source-to-evidence workflow around an individual public claim.

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

This demonstration tests the adapter and fixture, **not** Chartography or any vendor headline. The adapter speaks OpenAI-compatible chat-completions; providers differ in supported parameters and token accounting. It does not implement official third-party evaluators. Each request is performed once without automatic retries; API fees are the user's responsibility. Local secrets are read from an environment variable, not written into artifacts. Only explicit loopback `http://` endpoints are supported; remote endpoints must use HTTPS.

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
