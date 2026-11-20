# GraphWalks: controlled Gemini 4 Neon execution

**Status as of 20 November 2026: implemented and locally tested, no Gemini inference performed.**

This adapter upgrades the independently byte-verified, MIT-licensed GraphWalks BFS candidate population from an offline grader to a cost-gated experimental runner. It has two distinct network stages and never generates a model answer by default.

## Inputs and trust boundaries

The commands accept the **complete original** `graphwalks_256k_to_1mil.parquet` from the pinned [openai/graphwalks snapshot](https://huggingface.co/datasets/openai/graphwalks/tree/be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7) and the `graphwalks-bfs-reference-index.jsonl` produced by our [byte-level audit workflow](https://github.com/fraware/model-claim-replay/actions/runs/44746523023). The runner verifies the exact Parquet SHA-256, BFS index SHA-256, all 200 prompt hashes, the node-set answers and source row identities **before contacting a provider**. Neither original prompts nor correct answers are committed to GitHub.

| Input | Required value |
|---|---|
| Dataset revision | `be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7` |
| Original Parquet SHA-256 | `537879431c72a42e3b500f80efc3047e7facb90390b6063d33679b4320985911` |
| BFS index SHA-256 | `250d80874ad9bc8edf278cf3bf7aa145da3f2b34967c5504b8fa8703358480ee` |
| Model ID | `gemini-4-neon` |
| API | Official SDK for countTokens; single-POST direct REST for paid Interactions |

## Install and download original data

```bash
python -m pip install -e '.[graphwalks]'
mkdir -p .runs/private/graphwalks
curl --fail --location --output .runs/private/graphwalks/graphwalks.parquet \
  'https://huggingface.co/datasets/openai/graphwalks/resolve/be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7/graphwalks_256k_to_1mil.parquet'
```

Download and extract `graphwalks-bfs-reference-index.jsonl` from the verified GitHub Actions artifact linked above. Preserve its `manifest.json` separately. The `claim-replay` commands verify the index and dataset bytes without trusting filenames.

## Stage 1: token counts only, no model generation

The next command transmits **one real prompt** to Google's `count_tokens` endpoint, verifies the input count and records an output allowance. It does not request a model-generated response. A Gemini API key is necessary and any provider-side billing or rate limitations remain subject to Google's terms.

```bash
export GEMINI_API_KEY='your-own-key'
claim-replay plan-graphwalks \
  --parquet .runs/private/graphwalks/graphwalks.parquet \
  --index .runs/private/graphwalks/graphwalks-bfs-reference-index.jsonl \
  --max-tasks 1 --max-output-tokens 16384 --thinking-level xhigh \
  --out .runs/private/graphwalks/one-task-plan.json
```

The plan contains *provider-returned* input token counts, context feasibility, per-task maximum reserved charges at the documented **standard** pricing of $3/M input tokens and $15/M output tokens (including thinking), and exact source SHA-256 bindings. It contains no prompt text or correct answers. The model has a **shared 1,048,576-token input+reasoning+output context** and a **32,768-token single-hop nonstreaming output ceiling**. Longer responses need a separately budgeted continuation protocol. Any input whose counted tokens plus requested output allowance exceed the context limit is marked blocked. The preflight is strictly preliminary until the provider confirms the actual context allocation. Changing the model, thinking level, source bytes or output allowance invalidates the plan.

## Stage 2: explicit, sequential paid execution

**Never run this stage without inspecting the plan and authorizing an explicit financial ceiling.** No paid calls are made in the project's CI workflows. For a one-task pilot:

```bash
claim-replay execute-graphwalks \
  --plan .runs/private/graphwalks/one-task-plan.json \
  --parquet .runs/private/graphwalks/graphwalks.parquet \
  --index .runs/private/graphwalks/graphwalks-bfs-reference-index.jsonl \
  --max-spend-usd 2.00 --execute-paid \
  --out .runs/private/graphwalks/one-task-run
```

The runner recounts tokens immediately before each request, refuses an altered count, validates context headroom, and checks a **worst-case per-request cost reservation** before contacting Google. It creates a durable intent record *before* the billable request. Each task is attempted at most once by the runner. If the process is interrupted after sending a request, that attempt remains unresolved; rerunning the same command **does not resend it**. Network errors are recorded without assuming they were free. Unknown provider-side effects, taxes, caching charges, pricing changes, network failures and financial account limits mean this is a **conservative application-side reservation, not a guarantee of the invoice amount**.

The private run directory holds response text, limited provider usage metadata and request receipts. It never uploads that text automatically. It is excluded by `.gitignore` under `.runs/`. The runner deliberately does **not** enable provider tools, web search or code execution; it sends the exact original prompt as a single, stateless input with the declared thinking level. No automatic retries occur.

## Export private model outputs and grade

```bash
claim-replay export-graphwalks \
  --plan .runs/private/graphwalks/one-task-plan.json \
  --run-dir .runs/private/graphwalks/one-task-run \
  --out .runs/private/graphwalks/one-task-responses.jsonl
claim-replay grade-graphwalks \
  --index .runs/private/graphwalks/graphwalks-bfs-reference-index.jsonl \
  --responses .runs/private/graphwalks/one-task-responses.jsonl \
  --index-sha256 250d80874ad9bc8edf278cf3bf7aa145da3f2b34967c5504b8fa8703358480ee \
  --dataset-revision be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7 \
  --out .runs/private/graphwalks/one-task-scores.json
```

A single task is a **diagnostic pilot**, not a reproduction of the publisher's 95.2% result. The score command preserves partial coverage, parser failures and API errors. The experiment must independently verify Google's exact dataset revision, 200-row selection, response postprocessing, sampling and model settings before claiming comparability. All runs remain self-reported until independently audited.

## Test coverage and reproducibility

`python -m unittest discover -s tests -p 'test_graphwalks_runtime.py' -v` checks hash mismatches, 200-row source-reference parity, context limits, budget reservations, invalid token counts, one-attempt-only execution, resume after ambiguous requests, invalid budgets, separate response export and offline F1. CI adds an actual synthetic `pyarrow` Parquet roundtrip and installs the official Gemini SDK, but performs **zero external model inference**.

## Authoritative API documentation

- [Gemini 4 Neon model limits](https://aistudio.google.com/docs/models/gemini-4-neon)
- [Thinking levels and shared context semantics](https://aistudio.google.com/docs/thinking)
- [Gemini token-counting API](https://aistudio.google.com/docs/tokens)
- [Gemini Interactions API](https://aistudio.google.com/api-reference/interactions-api)
- [Current Gemini developer pricing](https://aistudio.google.com/docs/pricing)

## Stateless provider request

The paid adapter explicitly submits `store=False`, `stream=False` and
`background=False` through Google's documented Interactions API.
It requests one foreground response per task, without server-managed
conversation continuity or an automatic retry. The combination is checked
by a dependency-free regression test. `store=False` disables persistent
Interactions conversation state; it **does not independently establish**
what provider-level data-retention or training policies apply.
See [Google's Interactions API documentation](https://ai.google.dev/gemini-api/docs/get-started).

## One-hop REST generation and retry restrictions

Paid generation calls Google's official
[`POST /v1beta/interactions`](https://aistudio.google.com/docs/get-started)
endpoint directly using `http.client.HTTPSConnection` with verified TLS,
the fixed Google hostname and `Api-Revision: 2026-05-20`. Each request
sets `store=false`, `stream=false`, `background=false` and
`service_tier=standard`. The `google-genai` SDK is retained **only for
the non-generative `count_tokens` preflight and pre-execution recount**.

This addresses Google's
[confirmed SDK retry defect](https://github.com/googleapis/python-genai/issues/3260).
Although Google closed the issue on 5 November 2026, a fixed direct REST
transport is independently auditable. There is no client-managed
continuation, redirect-following, polling, or automatic retry. HTTP
failures are recorded as potentially billable attempts under the durable
journal. A single client-level POST does not guarantee server-side billing
or account-level cost ceilings.

The official REST response has `steps` containing a `model_output` with
text content. The parser admits only one completed model-output step,
the correct model identity, and valid token usage. Incomplete or
`requires_continuation` responses are **unscored**. It never copies
partial continuation tokens or reasoning signatures to public artifacts.
One-hop nonstreaming output is limited to **32,768 tokens**.

A loopback HTTP integration test verifies exact JSON fields, request
headers, a single POST, 429 responses without retries, redirect rejection,
usage accounting, malformed results and model-identity checks. It never
calls the real provider and uses no API credentials. The provider's data
retention and training policies are separate from `store=false`.

## Freshness and explicit pricing tier

The execution planner records a timezone-aware UTC creation timestamp.
An execution plan more than 24 hours old, or more than five minutes
future-dated, is rejected. The paid request sets `service_tier='standard'`
explicitly and the plan must match the documented standard $3/$15 per
million-token pricing assumptions. Rebuild the plan if provider prices
or evaluation configuration change. Actual invoices and account quotas
remain under the provider's control.
