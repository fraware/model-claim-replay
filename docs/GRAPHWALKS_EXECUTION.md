# GraphWalks: controlled Gemini 4 Neon execution

**Status as of 23 November 2026: source-bound Gemini token counting succeeded for two public candidate prompts; no model generation performed. One long-context candidate exceeds the model's declared context limit.**

This adapter upgrades the independently byte-verified, MIT-licensed GraphWalks BFS candidate population from an offline grader to a cost-gated experimental runner. It has two distinct network stages and never generates a model answer by default.

## First authenticated model token-count evidence — 23 November 2026

The [first live Gemini provider token-count run](https://github.com/fraware/model-claim-replay/actions/runs/45156733056) authenticated `GEMINI_API_KEY`, verified the original public Parquet and its BFS index byte-for-byte, and counted **two prespecified public candidate inputs**. It used `gemini-4-neon`, `xhigh` thinking for a hypothetical subsequent experiment, and an **8,192-token future output allowance**. No model completion was requested.

| Original BFS source task | Provider-reported input tokens | Conservative input + output allowance | Feasibility under declared 1,048,576-token context |
|---|---:|---:|---|
| `bfs-row-000100` (shorter band) | 355,124 | 363,316 | Within declared context |
| `bfs-row-000300` (longer band) | 1,419,783 | 1,427,975 | Exceeds declared context |

The longer prompt exceeds the declared context limit by **371,207 input tokens**, even if zero output tokens are reserved. This invalidates that candidate for the prescribed execution configuration. Shrinking the output cap cannot repair an input-only overflow. The token plan reports **one of two blocked** and a combined hypothetical worst-case reservation of **$5.570481**; this is *not* observed billing, authorization, or evidence of generation. The original JSON token plan has SHA-256 `552f98fd33a53f585362abaee989c601c7754f48008792255c963cd45449f92f` and is retained as the run's redacted Actions artifact.

These values establish feasibility for **two selected candidates only**. They do not identify Google's private 200-task selection, validate the publisher's exact input construction or imply a model F1 result. A [separate prespecified 20-task non-generative scan](../.github/workflows/graphwalks-live-token-count.yml) will examine the extent of the constraint, along with the provider-advertised model limits.

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

## One-click, token-count-only GitHub preflight

The repository includes a manually triggered
[GraphWalks Gemini token preflight workflow](https://github.com/fraware/model-claim-replay/actions/workflows/graphwalks-token-preflight.yml).
Add a repository Actions secret named `GEMINI_API_KEY` through
**Settings → Secrets and variables → Actions → New repository secret**,
then choose **Actions → GraphWalks Gemini token preflight → Run workflow**.
The default counts **one** pinned BFS task. Other explicit choices count
2, 5, 20, or all 200 tasks; the two-task choice samples both public input bands but the first live preflight found its selected long-context task outside the model's declared context limit. The **one-task short-context selection** is the default for a potential context-feasibility-screened diagnostic. All paid runs still need explicit financial authorization. Both preflight and paid workflow accept a
65,536-token maximum output allowance, subject to the same context gate. For multi-task preflights the selected records
are deterministically balanced across the two public input-length bands.

The workflow retrieves the exact public source file, recomputes its SHA-256,
rebuilds the 200-task reference index, verifies its pinned digest, and sends
the selected original prompts to the Gemini **token-count** endpoint.
It performs **no model generation** and never invokes
`execute-graphwalks`. It uploads only a JSON token-count and maximum-cost
plan, retained for up to 90 days (subject to repository retention settings);
no source Parquet, reference answers,
source prompt text or API keys are included in the uploaded artifact.

**Security and limitation:** The secret is passed only to the token-count
step. GitHub-hosted runners and the provider process the prompt text under
their respective terms. The workflow does not claim that token counting
has zero provider-side cost; it performs no inference request. API access,
quotas, provider availability, and precise token accounting remain external.
The repository cannot install an Actions secret on the owner's behalf.

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

The plan contains *provider-returned* input token counts, context feasibility, per-task maximum reserved charges at the documented **standard** pricing of $3/M input tokens and $15/M output tokens (including thinking), and exact source SHA-256 bindings. It contains no prompt text or correct answers. The model has a **shared 1,048,576-token input+reasoning+output context** and a **65,536-token synchronous one-hop output ceiling**. Longer responses need a separately budgeted continuation protocol. Any input whose counted tokens plus requested output allowance exceed the context limit is marked blocked. The preflight is strictly preliminary until the provider confirms the actual context allocation. Changing the model, thinking level, source bytes or output allowance invalidates the plan.

## Manual GitHub pilot with two separate authorization gates

For a credential-owning maintainer, the
[GraphWalks paid diagnostic workflow](https://github.com/fraware/model-claim-replay/actions/workflows/graphwalks-paid-pilot.yml)
provides a controlled path through source verification, model-specific
token-count preflight, paid generation, journal audit, private-response
export, and the original F1 scorer. **This workflow has not been executed
against the live provider.** It is deployed infrastructure, not experimental
evidence of any model's performance.

Set a repository Actions secret named `GEMINI_API_KEY`, then navigate
to **Actions → GraphWalks paid diagnostic → Run workflow**. The form
defaults to `approval=NO` and `max_spend_usd=0`, deliberately
blocking billable requests. To authorize one run, set a **positive
finite USD ceiling no greater than $100** and type the exact phrase
`AUTHORIZE_PAID_GEMINI`. Choose 1, 2, 5, or 20 tasks and a
per-task output allowance of 8,192, 16,384, 32,768, or 65,536 tokens. The default remains 16,384 for a lower-cost diagnostic; the 65,536-token choice is the published foreground limit, not evidence that Google used that exact allowance.
Two tasks is the recommended first diagnostic: one from each
verified source-length cohort.

The first check rejects missing consent, invalid budgets and missing
credentials *before downloading the approximately 297 MB public source*.
After SHA-256 validation and provider-side token counting, the second
check rejects any infeasible context, mismatched cohort size or total
maximum cost reservation above the authorized budget. The paid runner
rechecks input token counts immediately before its single-attempt
generation calls. A 24-hour freshness limit applies to token plans.
The $100 ceiling is an application-side authorization cap, **not an
invoice guarantee**; provider accounting, taxes, price revisions and
external account limits are not under this project's control.

The public GitHub Actions artifact is limited to the **score-free token
plan**, the **redacted local journal audit**, and the **per-task F1 report**
(each remains self-reported and not comparable to the publisher). The
original source Parquet, gold answer index, private model-response
journal, raw predictions and credential never enter that artifact.
GitHub-hosted runners and the model provider still process those
private files under their own service policies. The execution step has a 330-minute timeout inside a 360-minute job. If it fails or times out after writing a durable request intent, the workflow attempts the independent audit even though the paid step failed. The redacted audit then records unresolved intents as potentially billable, with no fabricated result. Scoring only proceeds if the execution step and audit both succeed. Before publishing grades, the workflow cross-checks the redacted plan, audit and scorer output using `claim-replay verify-graphwalks-public` and generates a source-bound standalone HTML report using `claim-replay report-graphwalks-public`. Its verification receipt, redacted HTML and source-faithful grades are published only if those checks pass; a failed attempt can instead publish the token plan and audit alone. Abrupt cancellation, runner loss, or exhaustion of the overall job timeout can still prevent any upload. The GitHub runner is ephemeral: absence of an artifact is not evidence that zero API calls occurred. Download the artifacts and review all statuses before drawing a conclusion.

For an entirely offline authorization audit, run:
`python -m unittest discover -s tests -p test_graphwalks_pilot_gate.py -v`.
These tests exercise the gate without a provider account.

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

The runner recounts tokens immediately before each request, refuses an altered count, validates context headroom, and checks a **worst-case per-request cost reservation** before contacting Google. It atomically publishes an fsynced intent record *before* the billable request.
An interrupted write cannot expose a truncated final intent or result as a
valid journal file. Temporary files used for publication reside outside the
audited attempts directory. The CLI takes a nonblocking, cross-process **POSIX advisory lock** for the full execution of one output directory. A concurrent runner using the same directory is rejected before it issues any request; the operating system releases this lock on process termination. A persistent hidden lock file in the output directory's parent is normal. **Paid execution is intentionally unavailable on platforms lacking POSIX locking.** A resumed run must pass the complete private-journal integrity audit, including all prior result and usage records, before any additional billable call. Locking coordinates cooperating local runners targeting the same canonical directory; independently named output directories have independent authorization and budgets. Each task is attempted at most once by the runner. If the process is interrupted after sending a request, that attempt remains unresolved; rerunning the same command **does not resend it**. Network errors are recorded without assuming they were free. Unknown provider-side effects, taxes, caching charges, pricing changes, network failures and financial account limits mean this is a **conservative application-side reservation, not a guarantee of the invoice amount**.

The private run directory holds response text, limited provider usage metadata and request receipts. It never uploads that text automatically. It is excluded by `.gitignore` under `.runs/`. The runner deliberately does **not** enable provider tools, web search or code execution; it sends the exact original prompt as a single, stateless input with the declared thinking level. No automatic retries occur.

## Export private model outputs and grade

```bash
claim-replay export-graphwalks \
  --plan .runs/private/graphwalks/one-task-plan.json \
  --index .runs/private/graphwalks/graphwalks-bfs-reference-index.jsonl \
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
One-hop nonstreaming output is limited to **65,536 tokens** for Gemini 4 Neon under Google's November 2026 model specification. The paid workflow defaults to a deliberately smaller **16,384-token allowance**. The allowance includes reasoning and final-answer tokens: a restricted diagnostic run can truncate a correct generation and does not establish the publisher's evaluation conditions.

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

## Audit private execution evidence before exporting answers

The new `claim-replay audit-graphwalks` command revalidates the local
self-reported execution ledger completely offline: the plan and pinned
200-task index, run manifest, unique task intents, matching response records,
per-task maximum budget commitments, token-usage types and unexpected files.
An interrupted request with an intent and no result remains explicitly
`unresolved`, distinct from a failed request and a task never attempted.

```bash
claim-replay audit-graphwalks \
  --plan .runs/private/graphwalks/one-task-plan.json \
  --index .runs/private/graphwalks/graphwalks-bfs-reference-index.jsonl \
  --run-dir .runs/private/graphwalks/one-task-run \
  --out .runs/private/graphwalks/one-task-audit.json
```

Private response export now requires `--index` and runs this audit
first. The audit contains per-file SHA-256 commitments without raw prompts,
answer lists or model responses. Historical runs remain auditable even
after the plan's 24-hour authorization to issue *new* provider requests
has expired. **Local hashing does not authenticate provider execution,
model identity or actual invoices.**

## Duplicate-record and budget-consistency controls

The shared JSONL reader already rejected duplicate or invalid task IDs
before the scorer constructed its task-ID lookup. Additional adversarial
tests now protect this existing trust boundary, including a duplicate
error record followed by a preferred successful completion. This
prevents last-record-wins scoring and selective response substitution.

The token planner rejects a zero-token count for a nonempty input and
rejects task counts larger than the verified cohort. Executable plans
must match the recorded task count, cumulative maximum reservation,
context-feasibility totals and non-comparable evidence status. A
completed response lacking the provider's input and output token
accounting is stored as an error, and the independent journal audit
refuses legacy records marked successful without that accounting.
These checks prevent locally inconsistent observations from appearing
as valid completed model evaluations. They are not remote attestation.

## Prespecified, balanced evaluation pilot

The SHA-256-verified public GraphWalks BFS index contains 200 rows in
**two context-length bands**, each with exactly 100 tasks. The first
band's prompt texts contain 437,563–437,639 characters, while the second
band contains 1,748,288–1,748,364 characters. These are not model token
counts.

The original prefix-based preflight drew all of the first 5 or 20 tasks
from the shorter-context band, systematically omitting the longer
problems. New plan schema `graphwalks-gemini-plan-v2` replaces that
choice with a deterministic, **balanced source-order sampling policy**,
`balanced_public_context_bands_v1`.

For `N` tasks, the policy selects `ceil(N/2)` shorter and
`floor(N/2)` longer tasks. Each band's positions are spread
uniformly over its 100 source entries, using the fixed
`floor(i * 100 / n)` rule for zero-based sample position `i`.
For example, a 20-task diagnostic pilot contains 10 tasks from each
band, while the full 200-task plan contains every original BFS task.
The plan records the policy and per-band counts, which are revalidated
before any paid request. A one-task connectivity preflight remains
a short-context diagnostic.

**Interpretation:** deterministic balancing reduces obvious coverage
bias in diagnostic subsets, but does not establish that Google's
publisher cohort is identical or that a small pilot estimates the
reported 95.2% with sufficient precision. Previously generated v1
plans require a new token-count preflight; they are not executable
under the v2 contract.
