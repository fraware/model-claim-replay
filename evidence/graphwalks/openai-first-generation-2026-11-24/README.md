# First live GPT-6.2 Sol diagnostic

One prespecified public GraphWalks BFS candidate: `bfs-row-000100`. Executed 24 November 2026 UTC by [GitHub Actions](https://github.com/fraware/model-claim-replay/actions/runs/45398852989) at commit `a3e9d484dabf02b34ddbd86ae633f50ffabbc0f1`. The archived ZIP is the original GitHub Actions artifact 14922527165, **2,847 bytes**, SHA-256:

```text
dd7834d6f3162ab2683d5cf39a382393dea1afcd0725ab03102ea252c7b24a07
```

The downloaded bytes were independently hashed and matched GitHub's digest. The archive contains exactly plan, intent, outcome, disclosed final-line evidence and verification JSON files. No reconstructed receipt is substituted for the original. The [website summary](../../../website/graphwalks-openai-result.json) is derived from these original bytes.

| Measurement | Value |
|---|---:|
| Completed scored tasks | 1 |
| Input tokens (provider reported) | 255,598 |
| Output tokens (provider reported) | 572 |
| Predicted nodes / reference nodes / intersection | 9 / 9 / 9 |
| F1 / precision / recall | 1.0 / 1.0 / 1.0 |
| Maximum generation reservation | $2.58871 |
| Conservative usage-cost estimate | $1.28943 |

## Recompute the disclosed-line score

Use the [source-audit artifact](https://github.com/fraware/model-claim-replay/actions/runs/44746523023), which contains the pinned 200-task BFS reference index. That downloaded source archive independently matched GitHub's SHA-256 `cf2d078035f3a4fe5a93aeaf8cf06f1c170751bc3e4fc2f2cd68a66a380bb9fe`. The index SHA-256 is `250d80874ad9bc8edf278cf3bf7aa145da3f2b34967c5504b8fa8703358480ee`.

If the source artifact expires, regenerate the index from the pinned public Parquet using the repository's source auditor:

```bash
python -m pip install -e '.[graphwalks]'
python scripts/graphwalks_data_audit.py \
  --revision be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7 \
  --sha256 537879431c72a42e3b500f80efc3047e7facb90390b6063d33679b4320985911 \
  --size-bytes 296903814 --retain-parquet --out .runs/reviewer-source
python -m zipfile -e evidence/graphwalks/openai-first-generation-2026-11-24/original-actions-artifact.zip .runs/reviewer-evidence
python -m model_claim_replay.openai_graphwalks_verify \
  --bundle .runs/reviewer-evidence \
  --index .runs/reviewer-source/graphwalks-bfs-reference-index.jsonl
```

Run from repository root. The ZIP extraction path must be a new directory. No OpenAI key or inference needed. The expected result is `score_recomputed_from_disclosed_final_line`, F1 = 1.0. Independently compute the overlap of the disclosed final-line node set and the reference node set for that source task to check the original grader.

## Scope

The workflow verifier agreed with a second calculation using separately downloaded, hash-checked artifacts in a separate environment. No external reviewer has yet reported a result. The full answer digest differs from the final-line digest, so extraction fidelity to the undisclosed answer is not proven by this archive. Provider execution and actual billed amount are not independently authenticated; cost is a conservative estimate. One public candidate task cannot establish population accuracy, absence of benchmark contamination, or equivalence to Google's evaluation. The [follow-up cohort](https://github.com/fraware/model-claim-replay/issues/42) is prespecified and not executed.
