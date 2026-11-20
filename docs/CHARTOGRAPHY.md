# Chartography reproduction dossier

**Status — unresolved access and publisher-protocol equivalence, as of 20 November 2026.** This dossier specifies a testable plan, not an independent reproduction of the claimed score.

## Published statement

Anthropic reports **Claude Fable 5.2, 73.4% on Chartography (no tools)**. This is a *publisher-reported number*. The original public announcement is [Anthropic's model-launch page](https://www.anthropic.com/claude-fable-and-mythos-5-2). The exact model snapshot, run parameters, dataset revision, sampling and judge settings for this figure have not been independently established.

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

## Decision gate

A completed import establishes that a local Inspect log contained internally consistent task/epoch score records. **A comparable reproduction needs independently validated correspondence to the exact published protocol**. The report always declares `not_comparable` at this stage, even for a complete grid. A discrepancy measured under a modified judge, private data subset, different model snapshot or undocumented settings is diagnostic evidence, not a refutation of Anthropic's statement.

## Open questions

- Is access to the official full task set obtainable for independent evaluation, and what forms of result publication are permitted?
- Which precise model ID, model snapshot, sampling settings and reasoning level produced 73.4%?
- Did the publisher use the exact public ten-epoch, Gemini-judge benchmark configuration?
- Can the benchmark author provide a dataset revision identifier and original evaluation provenance for comparison?
- What financial budget and concurrent API quotas are needed for a full repeated experiment?
