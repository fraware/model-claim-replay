# Automation lifecycle

[Documentation home](README.md)

CI and site deployment are ordinary development operations. Provider metadata and input counting are non-generative operations that need credentials; they are distinct from paid inference. Paid requests need separate explicit approval, source verification and budget checks. Reservation estimates are not provider-enforced account caps.

| Workflow | Role and lifecycle |
|---|---|
| [ci.yml](../.github/workflows/ci.yml) | Active: push/PR tests, packaged demo, browser and mock integrations. |
| [pages.yml](../.github/workflows/pages.yml) | Active: static site deployment. |
| [provider-readiness.yml](../.github/workflows/provider-readiness.yml) | Active: main-only OpenAI model metadata probe. |
| [graphwalks-data-audit.yml](../.github/workflows/graphwalks-data-audit.yml) | Source audit: pinned dataset and reference index. |
| [graphwalks-algorithmic-control.yml](../.github/workflows/graphwalks-algorithmic-control.yml) | Deterministic source control; zero model generation. |
| [graphwalks-preflight.yml](../.github/workflows/graphwalks-preflight.yml) | Historical feasibility checks. |
| [graphwalks-live-token-count.yml](../.github/workflows/graphwalks-live-token-count.yml) | Historical Gemini live count experiment. |
| [graphwalks-token-preflight.yml](../.github/workflows/graphwalks-token-preflight.yml) | Manual Gemini token-count preflight. |
| [graphwalks-paid-pilot.yml](../.github/workflows/graphwalks-paid-pilot.yml) | Manual Gemini diagnostic; no standing spending authorization. |
| [graphwalks-openai-preflight.yml](../.github/workflows/graphwalks-openai-preflight.yml) | Main-only, workflow-change-triggered OpenAI count-only diagnostic. |
| [graphwalks-openai-paid.yml](../.github/workflows/graphwalks-openai-paid.yml) | Manual OpenAI one-task diagnostic; default preflight-only. |
| [graphwalks-openai-first-generation.yml](../.github/workflows/graphwalks-openai-first-generation.yml) | Historical one-time $5 pilot; authorization consumed. |
| [graphwalks-openai-campaign-preflight.yml](../.github/workflows/graphwalks-openai-campaign-preflight.yml) | Frozen 16-task count-only preflight; completed. |
| [graphwalks-openai-campaign-authorized.yml](../.github/workflows/graphwalks-openai-campaign-authorized.yml) | Completed one-time $25 campaign; authorization consumed. See [observed results](OPENAI_CAMPAIGN.md#observed-results). |
| [graphwalks-openai-campaign-paid.yml](../.github/workflows/graphwalks-openai-campaign-paid.yml) | Retired manual dispatch for the frozen cohort; rejects execution. |

| [stage-release-draft-once.yml](../.github/workflows/stage-release-draft-once.yml) | Temporary branch-only unpublished release draft staging; removed after execution. |

Historical workflow files remain for traceability and regression checks. Never rerun a consumed paid authorization, including after an ambiguous failure or interruption. An intent lacking a terminal outcome is an unresolved request, not a zero score. Preserve original source and run commitments.

The canonical execution instructions are in [OpenAI campaign](OPENAI_CAMPAIGN.md), [the one-task evidence archive](../evidence/graphwalks/openai-first-generation-2026-11-24/README.md) and [Gemini execution](GRAPHWALKS_EXECUTION.md).
