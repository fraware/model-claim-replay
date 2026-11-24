# Frozen 16-task OpenAI GraphWalks campaign

[Prespecified protocol and selection](https://github.com/fraware/model-claim-replay/issues/42) · [Original live preflight](https://github.com/fraware/model-claim-replay/actions/runs/45401394821) · [Original preflight ZIP](../evidence/graphwalks/openai-campaign-preflight-2026-11-24.zip)

The preflight completed 24 November 2026 UTC. All 16 counts were observed. Eight shorter inputs fit (255,149–255,652 tokens); all eight longer inputs exceed the 922,000 input limit (1,022,153–1,022,892 tokens). Feasible generation reservation: **$20.699335** at $5/M input and $20/M output planning rates. No model generation occurred in that preflight. The ZIP is byte-identical to the downloaded original artifact (SHA-256 `622dc133c231e7f14562037f4d2094916054aae991b43fd83ab31dcbf27ac853`).

## Paid follow-up

The [manual campaign workflow](https://github.com/fraware/model-claim-replay/actions/workflows/graphwalks-openai-campaign-paid.yml) requires separate `AUTHORIZE_OPENAI_CAMPAIGN` selection and a fixed $25 aggregate reservation ceiling. Default approval is NO; publication defaults to REDACTED_ONLY. Choose PUBLISH_FINAL_LINE only with explicit consent to publish the restricted canonical answer lines. The earlier $5 pilot authorization is consumed and cannot authorize this campaign. The $25 ceiling is an estimated reservation, not a provider-enforced invoice cap.

Freshly verify the pinned source and recount all selected prompts. Any change in counts, feasibility, or reservations stops the campaign before generation. The eligible eight tasks run sequentially in frozen order; the blocked eight retain terminal records. No automatic retries. Unexpected accounting or response structure stops further generation; incomplete or refused responses with validated accounting are recorded separately from malformed completed answers. A timeout or cancellation can leave an intent without a terminal record; never rerun automatically and do not claim complete accounting in that case.

Report conditional F1 only for graded tasks, separately by source band; an aggregate covering all 16 is unavailable when any task is ungraded. Full provider responses are not uploaded. Final-line score verification is conditional on faithful extraction; external authentication and actual invoices remain unverified.

No cohort generation is authorized or claimed by this document.
