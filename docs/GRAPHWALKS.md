# Gemini 4 Neon / GraphWalks long-context BFS

**Source-registered candidate, not a reproduced result — updated 23 November 2026.**

Google DeepMind's 18 November 2026 [Gemini 4 Neon model card](https://deepmind.google/models/model-cards/gemini-4-neon/) reports **95.2% F1** on GraphWalks breadth-first search with contexts from **256K to 1M tokens**. Its [evaluation methodology](https://deepmind.google/models/evals-methodology/gemini-4-neon) states that this was a self-computed evaluation on **200 GraphWalks problems**. The general methodology specifies Gemini API execution with highest thinking settings, pass@1 except where noted, and safety filters enabled outside cybersecurity evaluations. It does not establish the exact prompt assembly, dataset snapshot, output parser, or number of GraphWalks repetitions.

## Live model-input feasibility finding (23 November 2026)

Our [authenticated, source-verified Gemini token-count diagnostic](https://github.com/fraware/model-claim-replay/actions/runs/45156733056) measured 355,124 input tokens for `bfs-row-000100` and 1,419,783 for `bfs-row-000300`, with no generated output. Under the runner's declared 1,048,576-token context limit, the second prompt is **371,207 input tokens over the limit**, even with zero output allowance. The original public source/index SHA-256 commitments and a redacted token-plan receipt are available in that run. This finding applies to the **sampled public candidate**, not necessarily to the unpublished 200-task cohort selected by Google.

The [byte-identical, hash-tested source-bound token plan](../evidence/graphwalks/gemini-4-neon-two-task-token-plan-2026-11-23.json) is permanently preserved with the original run URL. The follow-up [20-task authenticated token-count run](https://github.com/fraware/model-claim-replay/actions/runs/45158739147) found **10/10 selected shorter-band tasks within the declared context** (354,061–355,228 input tokens), and **10/10 selected longer-band tasks exceeding** the provider-advertised 1,048,576-token input limit (1,419,201–1,420,389 input tokens). The same endpoint reported a separate 65,536-token output limit. These are prespecified public-candidate measurements, not publisher-cohort results or model F1. The [complete authenticated 200-task candidate scan](https://github.com/fraware/model-claim-replay/actions/runs/45159511810) resolved sampling uncertainty: **100/100 shorter-band tasks fit** (354,061–355,496 tokens); **100/100 longer-band tasks exceed the provider's input limit** (1,419,001–1,420,682 tokens), even without reserved output. All source-bound token counts and their [byte-identical original plan](../evidence/graphwalks/gemini-4-neon-full-200-token-plan-2026-11-23.json) are published in the [compact public receipt](../website/graphwalks-gemini-feasibility.json). The reported $556.982841 maximum is hypothetical generation cost, not incurred spending. These results demonstrate **candidate input infeasibility** for the long band under the declared API configuration; the publisher's exact 200-item selection, model input construction, and score remain unverified.

## Why this is an important second candidate

Unlike the private Chartography task population, the original [openai/graphwalks dataset](https://huggingface.co/datasets/openai/graphwalks) is published on Hugging Face with an **MIT** license. The task prompts represent graphs as edge lists and request node-set outputs. A public benchmark permits external dataset pinning, item accounting and deterministic local scoring without reverse engineering a private chart judge.

The data is not automatically equivalent to Google's evaluated population. We verified a public candidate revision containing **exactly 200 BFS task identities** and reference answers. We must still establish Google's actual dataset revision, source population and other conditions before a publisher-level comparison. The public dataset has a documented [correction history](https://huggingface.co/datasets/openai/graphwalks/commit/0846d2b457dde704491be44cebd9d0d7409660b3). Evaluating a different revision could change the score.

## Feasibility risks

- **Cost.** A 200-task full run at 256K–1M input tokens per task is potentially expensive. Obtain real task token counts under the target model's tokenizer and an actual API price quote before authorization.
- **Provider execution.** Verify Gemini 4 Neon's supported API model identifier, context length, thinking parameters, rate limits and output-token limits.
- **Metric fidelity.** Source the original node-set extraction and F1 aggregation. Explicitly handle duplicate nodes, non-answers, malformed outputs and failed API calls under the benchmark's actual rules. A home-grown grader is not a reproduction.
- **Evaluation population.** Pin source dataset revision and file SHA-256, and identify exact included BFS rows. Merely selecting the first 200 public records would be unjustified.
- **Comparability.** A smaller pilot or shorter-context task is valuable for engineering but cannot confirm or refute the 95.2% result.

## Execution gates

1. Snapshot the public MIT dataset, record repository revision and SHA-256, and derive a reproducible 200-item selection with independent checks of task type and context length.
2. Reconcile Google's complete run settings with an official or benchmark-authored evaluator and grade semantics.
3. Establish the total token budget using exact task input sizes and provider pricing; preflight API access without committing to a full experiment.
4. Implement a separate GraphWalks adapter (do not route this claim through the Chartography Inspect importer), with deterministic output parsing, per-task traces and score verification.
5. Run a declared, inexpensive integration pilot. Only consider a full 200-task comparison if the previous gates have passed, with results reported regardless of agreement.

**Current status:** original claim sourced, all 296,903,814 bytes of the candidate long-context Parquet independently verified, 200 BFS task references extracted and the upstream grader tested offline. No model inference or publisher-equivalent reproduction has been completed.

## Source records

- [Google DeepMind model card, 18 November 2026](https://deepmind.google/models/model-cards/gemini-4-neon/)
- [Google DeepMind evaluation methodology (PDF)](https://deepmind.google/models/evals-methodology/gemini-4-neon)
- [OpenAI GraphWalks dataset and license](https://huggingface.co/datasets/openai/graphwalks)
- [OpenAI dataset revision history](https://huggingface.co/datasets/openai/graphwalks/commits/main)

## Pinned public data snapshot (metadata-only)

The automated [GraphWalks source preflight](https://github.com/fraware/model-claim-replay/actions/runs/44744877596)
fetched a public Hugging Face API metadata receipt on **20 November 2026 at 13:30 UTC**.
It recorded dataset repository revision
`be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7`, MIT license and:
- `graphwalks_256k_to_1mil.parquet`: **296,903,814 bytes**, upstream LFS SHA-256
  `537879431c72a42e3b500f80efc3047e7facb90390b6063d33679b4320985911`
- `graphwalks_128k_and_shorter.parquet`: **22,128,284 bytes**, upstream LFS SHA-256
  `54036036c91d8e04bb2a5fcd9e36f8e2a852cacece5dfc2b1ee40e3a6182b516`

These sizes and digests were *reported by the upstream API*, not recomputed
from downloaded Parquet bytes. The receipt is downloadable as the
`graphwalks-public-metadata` artifact from the linked CI run, retained for
14 days. No selected 200-task cohort or Google-specific dataset revision has
been established.

## Offline F1 scorer

The dataset's [MIT-licensed grading reference](https://huggingface.co/datasets/openai/graphwalks/blob/be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7/README.md)
specifies a final-line `Final Answer: [...]` parser and set-overlap F1.
The `grade-graphwalks` command implements this exact extraction and per-sample
scoring convention. **It is an offline grader, not an inference runner.**

Use a purpose-built *reference index* containing one JSONL object with
`id`, `problem_type: "bfs"` and `answer_nodes: ["..."]` per task.
The index must be explicitly hashed and prepared from an authorized source
dataset with its independent revision record. Responses have the schema
`{"id":"...","status":"ok","output":"Final Answer: [...]"}` or
`{"id":"...","status":"error"}`. API errors/missing rows block the complete
mean; malformed model text receives F1=0 according to the benchmark card.
The output reports local scoring and SHA-256 commitments only, and never
publishes raw prompts, gold answer nodes or model response content.

**Synthetic, two-task demonstration** (the all-zero revision is a fixture
marker, not a real dataset commit):

```bash
claim-replay grade-graphwalks \
  --index examples/graphwalks-demo-index.jsonl \
  --responses examples/graphwalks-demo-responses.jsonl \
  --index-sha256 b39f93f5828a11ba43a72bcd0e456a93933ef8a8155d206e19053b89801b57b4 \
  --dataset-revision 0000000000000000000000000000000000000000 \
  --out .runs/graphwalks-synthetic.json
```

This demo produces F1 of 5/6 across two **synthetic** reference records.
It does not reproduce Gemini 4 Neon's 95.2%.

## Byte-verified long-context public cohort — 20 November 2026

The [full data audit](https://github.com/fraware/model-claim-replay/actions/runs/44746523023)
downloaded and SHA-256 verified the entire public MIT-licensed long-context
Parquet at candidate commit `be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7`.
The file is **296,903,814 bytes** with verified SHA-256
`537879431c72a42e3b500f80efc3047e7facb90390b6063d33679b4320985911`.

Parsing the verified file returned **400 rows, consisting of 200 BFS and 200
parent-node tasks**. The BFS-only index contains 200 unique source row IDs,
SHA-256 hashes of each actual prompt, and original reference node lists.
Its independently checked SHA-256 is
`250d80874ad9bc8edf278cf3bf7aa145da3f2b34967c5504b8fa8703358480ee`.
The [workflow artifact](https://github.com/fraware/model-claim-replay/actions/runs/44746523023)
contains the index and an audit manifest. Raw prompts are excluded.
The source auditor reproduces this index from the pinned Parquet.

The 200 BFS prompts range from **437,563 to 1,748,364 actual characters**.
Each BFS record's `prompt_chars` field is **138 characters shorter** than
the actual current prompt text. This systematic discrepancy was verified
across all 200 rows; its cause remains unresolved. API usage estimates must
use actual prompt bytes and model-specific tokenization.

**Scope:** The public BFS count matches the 200 problems in Google's
methodological description. We have not established that Google used this
candidate revision or this exact population. No result from the model itself
was measured.

## Model API cost preflight

Google's [developer pricing](https://ai.google.dev/gemini-api/docs/pricing)
lists `gemini-4-neon` at **$3 per million standard input tokens** and
**$15 per million output tokens**, including thinking tokens, as checked
20 November 2026. The batch rate is $1.50 per million input and $7.50
per million output tokens. Conditional on Google's stated 256K–1M token
range, 200 inputs imply 51.2–200 million tokens, or roughly **$154–$600
in standard input charges alone**. This is not a run quotation: exact
token counts, outputs, retries and applicable provider limits are unmeasured.

Use the archived index to score privately recorded model responses offline:

```bash
claim-replay grade-graphwalks \
  --index graphwalks-bfs-reference-index.jsonl \
  --responses /private/recorded-model-responses.jsonl \
  --index-sha256 250d80874ad9bc8edf278cf3bf7aa145da3f2b34967c5504b8fa8703358480ee \
  --dataset-revision be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7 \
  --out /private/graphwalks-scored.json
```

The evaluator is source-faithful, yet it cannot verify the model inputs,
provider identity, original publisher cohort, or execution conditions.
All offline score reports are explicitly `not_comparable` to the 95.2% claim.

## Experimental execution adapter

The [controlled GraphWalks execution guide](GRAPHWALKS_EXECUTION.md) documents
how to verify all 200 public BFS prompt bytes, obtain actual provider token
counts without requesting generation, and run explicitly authorized sequential
API calls under a conservative budget reservation. The adapter records a durable
intent before each request and never automatically retries interrupted requests.
The original offline F1 grader remains separate. No Gemini inference has yet
been executed, and exact equivalence to Google's 95.2% evaluation is unresolved.

## Public evidence explorer

The [interactive GraphWalks audit](https://fraware.github.io/model-claim-replay/graphwalks.html) displays all **200 SHA-256-verified candidate BFS items**, their source row IDs, prompt-character lengths, and SHA-256 commitments without exposing the underlying prompt or reference-node content. It is generated from the pinned index using `scripts/publish_graphwalks_summary.py` with an independently checked source-index digest. Its two equal-sized bands distinguish shorter and longer inputs by a **1,000,000-character threshold**, not by model tokens. The explorer is an inspectable source-data record and cannot be interpreted as a model performance measurement.

## Independent algorithmic control — 21 November 2026

A dedicated [model-free GraphWalks control](GRAPHWALKS_CONTROL.md)
executed against the original 200 pinned long-context BFS prompts.
Ordinary deterministic graph parsing and BFS achieved **200/200
parsed tasks and F1 = 1.0 for each**, as verified by the
[GitHub Actions run](https://github.com/fraware/model-claim-replay/actions/runs/44884895995)
and its [per-task report](../website/graphwalks-control.json). This
confirms internal consistency of source graph prompts and reference
answers under an algorithmic solver. It is **not a Gemini model
evaluation**, does not reproduce the publisher's 95.2%, and does not
establish equivalence to the publisher's dataset revision or inference
conditions. An existing [FalkorDB graph/LLM proxy](https://github.com/FalkorDB/GraphWalks)
is acknowledged as adjacent prior art.
