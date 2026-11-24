# Usage

[Documentation home](README.md) · [Project README](../README.md)

The default package has no third-party runtime dependencies. Python 3.10+ and Git are needed for the GitHub installation. The optional Inspect and GraphWalks source-audit integrations have additional dependencies. Paid model execution is always a distinct operation.

## Offline quickstart

```bash
python -m pip install "git+https://github.com/fraware/model-claim-replay.git"
claim-replay demo
```

Open `.runs/demo/report.html`. All three responses are synthetic; the expected accuracy is 2/3. The output directory must be new. For a different path use `claim-replay demo --out local-demo`. To verify the original demo bundle:

```bash
claim-replay verify .runs/demo/run --claim .runs/demo/claim.json --tasks .runs/demo/tasks.jsonl
```

## Check local artifacts in a browser

Open the [browser checker](https://fraware.github.io/model-claim-replay/check.html). Select the original run manifest, claim manifest and results file. For portable-text evidence, also select the original task data. Inspect bundles support an optional original source log. Files stay in the browser; this checks commitments, not full schema validity, scores or provider origin. Use the CLI verifier for the complete supported local checks.

## Work from a source checkout

### Import and report fixed responses

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

Run commands referring to `claims/` or `examples/` from the repository root. For the following optional integrations, install the relevant extras from that checkout.

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

The importer rejects corrupted score types, duplicate task/epoch records, inconsistent original aggregate scores for complete reference grids, and incompatible task identities. It reports precise coverage and preserves *pseudonymous* task-level scores, source log SHA-256, recorded judge/dataset/model metadata and unresolved protocol differences. It does not export private charts, prompts, gold answers, raw responses or judge rationales. **A successful import is not an independent reproduction.** See the [Chartography reproduction dossier](CHARTOGRAPHY.md) for upstream code revision, access constraints and full evaluation protocol.

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

## Call a real model using the portable runner

For a claim with a pinned *text-only exact-match* dataset and compatible declared conditions:

```bash
# Set OPENAI_API_KEY in your environment using your local secret manager.
claim-replay run \
  --claim claims/demo-text-exact-match.json --tasks examples/demo-tasks.jsonl \
  --model YOUR_MODEL_ID --base-url https://api.openai.com/v1 \
  --limit 3 --out .runs/local-model
```

This demonstration tests the adapter and fixture, **not** Chartography or any vendor headline. The adapter speaks OpenAI-compatible chat-completions; providers differ in supported parameters and token accounting. It does not implement official third-party evaluators. Each request is performed once, without redirect following or automatic retries; responses stopped by length limits, content filtering or tool handoffs are not silently graded as completed answers. API fees are the user's responsibility. Local secrets are read from an environment variable, not written into artifacts. Only explicit loopback `http://` endpoints are supported; remote endpoints must use HTTPS.

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

Both records and the revision marker above are **synthetic**. The 5/6 F1 is a fixture result, not a model evaluation. For a real source-index format, correct score semantics and the pinned HF metadata snapshot, see [the GraphWalks dossier](GRAPHWALKS.md).

## GraphWalks provider experiments

For the original OpenAI one-task diagnostic, use the [archived evidence instructions](../evidence/graphwalks/openai-first-generation-2026-11-24/README.md). The [frozen OpenAI campaign](OPENAI_CAMPAIGN.md) documents the separate 16-task selection and offline journal verifier. Its authorization is consumed by first introduction on main; never redispatch or rerun it.

The [historical Gemini execution guide](GRAPHWALKS_EXECUTION.md) describes the distinct Gemini-specific runner, including explicit token and spending controls. The [redacted receipt contract](GRAPHWALKS_PUBLIC_RECEIPTS.md) describes consistency checking for that format. Neither is a reproduction of a publisher aggregate.

## Interpret your report

### Evidence fields

| Report field | Interpretation |
|---|---|
| Publisher-reported result | A sourced claim, never inferred from a local score |
| Observed result | Exact-match score recomputed against pinned tasks |
| Task accounting | Passed, failed, API errors, total and attempted counts |
| 95% Wilson interval | Descriptive only under i.i.d. Bernoulli assumptions; may be inappropriate for correlated tasks |
| Content SHA-256 | Detects accidental artifact changes, **not** fraudulent or unauthenticated runs |
| Comparison status | `not_comparable` for published claims without authenticated protocol equivalence; Inspect pairs receive `paired_diagnostic_only` or `blocked` |

See [the methodology](METHODOLOGY.md) for limitations, publication standards, trust boundaries and why a subset is never represented as a full reproduction.
