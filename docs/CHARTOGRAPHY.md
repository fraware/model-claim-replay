# Chartography reproduction dossier

**Status — unresolved access and publisher-protocol equivalence, as of 20 November 2026.** This dossier specifies a testable plan, not an independent reproduction of the claimed score.

## Published statement

Anthropic reports **Claude Fable 5.2, 73.4% on Chartography (no tools)**. This is a *publisher-reported number*. The original public announcement is [Anthropic's model-launch page](https://www.anthropic.com/claude-fable-and-mythos-5-2). Anthropic's announcement identifies the result as **without tools**, using its **highest available effort**, with safeguards enabled unless otherwise noted. The exact model snapshot, run parameters, dataset revision, sampling and judge settings behind this figure have not been independently established.

## Original benchmark

The upstream implementation is [surge-ai/chartography](https://github.com/surge-ai/chartography) and its source was examined at commit [`3f1bf837232d3918c2cc35c6e2418c9e70d2a57b`](https://github.com/surge-ai/chartography/tree/3f1bf837232d3918c2cc35c6e2418c9e70d2a57b).

Upstream documents:
- `chartography` is an [Inspect AI](https://inspect.aisi.org.uk/) task with image prompts, a model response and a separate model judge (`src/chartography/task.py`, `scorer.py`).
- The scorer returns `accuracy` as a binary **0 or 1** per task-epoch. Judge failures return unscored values and must not be treated as model errors or model mistakes.
- The upstream README identifies the leaderboard reference as **100 tasks × 10 epochs**, judged by `google/gemini-3.5-flash`, with the mean `accuracy/mean` used as pass@1. This is the benchmark author's reference, *not yet proof of the publisher's exact protocol*.
- The GitHub repository includes **two local dummy tasks** for smoke tests, explicitly excluded from the full benchmark.
- The full dataset is referenced as `surgeai/chartography` on Hugging Face. An anonymous attempt to open that endpoint returned HTTP 401 (authorization required or otherwise unavailable); task access and redistribution rights must be established with the benchmark owner. Dataset content is not included in Model Claim Replay.
- The upstream code repository has no declared top-level license at the time of examination. Our source links and Inspect importer do not vendor upstream code or images.

## Reproduction preparation

1. Obtain documented authorization for the full dataset and permitted publication of score-only evidence. Contact the benchmark maintainer, [benchmarks@surgehq.ai](mailto:benchmarks@surgehq.ai), with questions on access and protocol.
2. Obtain exact model ID, evaluator revision, reasoning level, output limits, sampling and judge configuration underlying **Anthropic's own 73.4%**. Record unresolved differences faithfully.
3. Clone upstream and check out the specific recorded Git commit. Install dependencies from its lockfile in an isolated environment. Review executable third-party code before running it.
4. Run a **mock-model smoke test on the two dummy tasks** to validate the execution environment, without reporting a reproduction score.
5. If permitted full data and provider access are available, execute the original no-tools task with a predeclared budget and all task repeats. Avoid changing any benchmark scorer, source prompt, judge or task exclusion without explicit disclosure.
6. Import the resulting original `.eval` or `.json` Inspect log using the CLI and verify its source digest. Publish a report with explicit protocol gaps and evidence licensing constraints.

The following is a **reference workflow**, not a verified command for an undisclosed model snapshot:

```bash
# In a separate checkout of the upstream chartography repository
# git checkout 3f1bf837232d3918c2cc35c6e2418c9e70d2a57b
uv run inspect eval src/chartography/task.py \
  --model <verified-provider-model-id> \
  --epochs 10 \
  --epochs-reducer "mean,pass_at_10,at_least_10" \
  -T hf_repo=surgeai/chartography \
  -T judge_model=google/gemini-3.5-flash

# In the Model Claim Replay environment, with the generated log on disk
python -m pip install -e '.[inspect]'
claim-replay import-inspect \
  --claim claims/claude-fable-5-2-chartography.json \
  --log /private/path/to/run.eval --out .runs/chartography
claim-replay verify .runs/chartography \
  --claim claims/claude-fable-5-2-chartography.json \
  --source-log /private/path/to/run.eval
claim-replay report .runs/chartography \
  --claim claims/claude-fable-5-2-chartography.json \
  --format html --output .runs/chartography-report.html
```

The CLI exports only a task pseudonym, epoch, score and selected safe header fields. It **does not copy** charts, licensed prompts, gold answers, model responses or judge explanations. The original log is retained locally; publishing its digest does not publish or authenticate its contents.

## Matched-run diagnostic comparison

To compare separate locally generated official Inspect logs from two models, import each into its own directory and use `claim-replay compare-inspect --claim ... --left ... --right ... --format html --output ...`. The comparison refuses missing scores, mismatched chart IDs, different epoch grids, missing recorded judge/dataset settings or unclean/unpinned harness metadata. A successful comparison describes only the supplied paired evidence. It does not establish parity with Anthropic's reported 73.4% or authenticate the original API outputs.

## Decision gate

A completed import establishes that a local Inspect log contained internally consistent task/epoch score records. **A comparable reproduction needs independently validated correspondence to the exact published protocol**. The report always declares `not_comparable` at this stage, even for a complete grid. A discrepancy measured under a modified judge, private data subset, different model snapshot or undocumented settings is diagnostic evidence, not a refutation of Anthropic's statement.

## Open questions

- Is access to the official full task set obtainable for independent evaluation, and what forms of result publication are permitted?
- Which precise model ID, model snapshot, sampling settings and reasoning level produced 73.4%?
- Did the publisher use the exact public ten-epoch, Gemini-judge benchmark configuration, or a distinct five-run or other internal protocol?
- Can the benchmark author provide a dataset revision identifier and original evaluation provenance for comparison?
- What financial budget and concurrent API quotas are needed for a full repeated experiment?

## CI verification of the official harness

The repository also tests a **pinned checkout of Surge AI's actual Chartography
implementation**, using the two public dummy tasks and Inspect's mock model for
both generation and judging. The GitHub Actions job `chartography-upstream-smoke`
invokes the benchmark's original `chartography` task and original scorer, imports
the resulting real `.eval` log and verifies the exported score-only bundle.
An unparseable mock-judge verdict is recorded as **unscored**, never as an
incorrect answer, and an all-unscored run has **no observed accuracy**. This is a
pipeline integration test, not a model comparison or a reproduction.

A separate [Chartography Harbor-format sample release](https://huggingface.co/datasets/surgeai/Chartography-harbor)
publishes two public tasks. Its dataset card explicitly states that the complete
100-task set needs direct arrangements with Surge AI. Its stated CC BY 4.0
coverage excludes third-party charts, and redistribution of those images is
restricted. The repository does not mirror either dataset.

### Inspect the automated score-only artifact

Successful GitHub Actions runs publish an artifact named `chartography-mock-evidence`
containing `run.json`, `results.jsonl`, `verified-summary.json`,
`report.html` and `README.md`. The package is retained for 14 days.
Download it from the [Tests workflow](https://github.com/fraware/model-claim-replay/actions/workflows/ci.yml).
Only scoring metadata leave CI. The two-task mock test measures no real model
and never constitutes reproduction of Anthropic's 73.4% claim.

### Logged dataset content

Paired-run comparisons require matching SHA-256 fingerprints of the logged
question, chart-image bytes and reference answer for every scored task and epoch.
A benchmark repository name, task ID and Git commit alone do not fix external
Hugging Face data. An image reference to an unpinned local file or URL cannot
satisfy this check. No image bytes, prompts or answers are included in exports.
This validates consistency of the logged inputs, not source dataset authenticity
or the original publisher's execution settings.
