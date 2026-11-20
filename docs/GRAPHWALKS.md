# Gemini 4 Neon / GraphWalks long-context BFS

**Source-registered candidate, not a reproduced result — 20 November 2026.**

Google DeepMind's 18 November 2026 [Gemini 4 Neon model card](https://deepmind.google/models/model-cards/gemini-4-neon/) reports **95.2% F1** on GraphWalks breadth-first search with contexts from **256K to 1M tokens**. Its [evaluation methodology](https://deepmind.google/models/evals-methodology/gemini-4-neon) states that this was a self-computed evaluation on **200 GraphWalks problems**. The general methodology specifies Gemini API execution with highest thinking settings, pass@1 except where noted, and safety filters enabled outside cybersecurity evaluations. It does not establish the exact prompt assembly, dataset snapshot, output parser, or number of GraphWalks repetitions.

## Why this is an important second candidate

Unlike the private Chartography task population, the original [openai/graphwalks dataset](https://huggingface.co/datasets/openai/graphwalks) is published on Hugging Face with an **MIT** license. The task prompts represent graphs as edge lists and request node-set outputs. A public benchmark permits external dataset pinning, item accounting and deterministic local scoring without reverse engineering a private chart judge.

The data is not automatically equivalent to Google's evaluated population. We must recover the exact **200 task identities**, benchmark revision, BFS-only selection, and ground-truth representation before any headline comparison. The public dataset has a documented [correction history](https://huggingface.co/datasets/openai/graphwalks/commit/0846d2b457dde704491be44cebd9d0d7409660b3). Evaluating a different revision could change the score.

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

**Current status:** original publisher claim sourced, public data catalog and terms identified, 200-problem methodological description verified. No source dataset download, fixed selection, API call, or numerical reproduction has been completed.

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
