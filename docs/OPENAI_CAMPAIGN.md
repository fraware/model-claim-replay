# Frozen 16-task OpenAI GraphWalks campaign

[Documentation home](README.md) · [GraphWalks dossier](GRAPHWALKS.md)

[Prespecified protocol and selection](https://github.com/fraware/model-claim-replay/issues/42) · [Original live preflight](https://github.com/fraware/model-claim-replay/actions/runs/45401394821) · [Original preflight ZIP](../evidence/graphwalks/openai-campaign-preflight-2026-11-24.zip)

The preflight completed 24 November 2026 UTC. All 16 counts were observed. Eight shorter inputs fit (255,149–255,652 tokens); all eight longer inputs exceed the 922,000 input limit (1,022,153–1,022,892 tokens). Feasible generation reservation: **$20.699335** at $5/M input and $20/M output planning rates. No model generation occurred in that preflight. The ZIP is byte-identical to the downloaded original artifact (SHA-256 `622dc133c231e7f14562037f4d2094916054aae991b43fd83ab31dcbf27ac853`).

## Paid follow-up

The owner separately approved the $25 campaign and restricted final-line disclosure on 24 November 2026. The [fixed one-time authorization](../evidence/graphwalks/openai-campaign-authorization-2026-11-24.json) binds the exact preflight archive and selection manifest, with at most eight generation requests. Its dedicated workflow triggers only on the record's first introduction to main, with history and digest checks prior to credential access. The overlapping manual workflow is retired for this cohort. Reusing an authorization, including after a failed or interrupted run, is prohibited. The earlier $5 pilot authorization is consumed. The $25 ceiling is an estimated reservation, not a provider-enforced invoice cap.

Freshly verify the pinned source and recount all selected prompts. Any change in counts, feasibility, or reservations stops the campaign before generation. The eligible eight tasks run sequentially in frozen order; the blocked eight retain terminal records. No automatic retries. Unexpected accounting or response structure stops further generation; incomplete or refused responses with validated accounting are recorded separately from malformed completed answers. A timeout or cancellation can leave an intent without a terminal record; never rerun automatically and do not claim complete accounting in that case.

Report conditional F1 only for graded tasks, separately by source band; an aggregate covering all 16 is unavailable when any task is ungraded. Full provider responses are not uploaded. Final-line score verification is conditional on faithful extraction; external authentication and actual invoices remain unverified.

Authorization is granted for this single campaign. No cohort result is claimed until the original execution evidence has been inspected. The model documentation was checked on 24 November 2026: 922,000 input-token limit, 1,050,000 total context and Standard long-context output rate $15/M; the frozen $20/M reserve remains an extra margin.

The runner stops admitting new generation requests after 290 minutes from its start, allowing additional time for the final response and upload under the job limit. This is an admission bound, not a guaranteed wall-clock transport timeout; interruption can still prevent a terminal record.

## Offline campaign journal verification

After obtaining the original campaign artifact, extract its ZIP into an empty directory, and use the independently regenerated, pinned reference index:

```bash
python scripts/verify_openai_campaign.py \
  --bundle /path/to/extracted-campaign \
  --index /path/to/graphwalks-bfs-reference-index.jsonl
```

The verifier rejects incomplete terminal journals, changed preflight measurements, unexpected files, mismatched intent records, incorrect cost arithmetic and inconsistent scores. It recomputes disclosed canonical final-line grades using independent set arithmetic. Withheld noncanonical scores are explicitly counted as not recomputed. The conditional means still summarize recorded grades; this is not authentication of provider execution, full-answer extraction, invoices or external review. A changed preflight or interrupted journal needs a separate investigation, not automatic retry.
