# Model Claim Replay

### The model is 40% better. Let's reproduce that.

**Published AI benchmark results deserve independently inspectable evidence.** Model Claim Replay is an open-source project to turn individual model-launch claims into reproducible experiments, with pinned inputs, declared execution protocols, independently rerunnable scoring, uncertainty, and shareable reports.

[Website source](website/) · [Methodology](docs/METHODOLOGY.md) · [Roadmap](docs/ROADMAP.md) · [Contribute](CONTRIBUTING.md)

> **Project status — foundation, not a completed benchmark replication.** The CLI executes pinned *portable text* fixtures, imports external response files, verifies content hashes, computes exact-match results, and generates standalone HTML/JSON reports. The registered Chartography claim is a real published statement, **not** a completed reproduction. Dataset access, licensing, model settings, judge protocol, and budget still need to be resolved before real comparison is justified. No provider result is invented.

**Website publishing:** A GitHub Pages deployment workflow is included. The repository owner must enable **Settings → Pages → Build and deployment → Source: GitHub Actions** once before the site has a public URL.

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
| Comparison status | `not_comparable` unless strict portable protocol conditions pass; even a match remains self-reported |

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

MIT-licensed source. **External benchmark datasets, models and evaluator implementations retain their original owners' terms** and are not redistributed by this repository.
