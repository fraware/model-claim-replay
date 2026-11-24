# GraphWalks: a deterministic graph control

[Documentation home](README.md) · [GraphWalks dossier](GRAPHWALKS.md)

This experiment evaluates **a specialized graph algorithm** on the pinned public GraphWalks BFS tasks. It is **not** an evaluation of Gemini 4 Neon, a reproduction of its reported 95.2% F1, or a new method for graph solving. It supplies a control for interpreting the benchmark: which source tasks are recoverable from the prompt by direct edge parsing and ordinary breadth-first search?

The public source is independently bound to the same 296,903,814-byte Parquet at [revision `be6cc6ec...`](https://huggingface.co/datasets/openai/graphwalks/tree/be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7) and SHA-256 `537879431c72a42e3b500f80efc3047e7facb90390b6063d33679b4320985911`, with the same 200-task BFS reference index digest `250d80874ad9bc8edf278cf3bf7aa145da3f2b34967c5504b8fa8703358480ee`.

## Mechanism

The algorithm removes explicitly delimited worked examples, accepts directed edge lines and one unambiguous BFS operation, constructs a directed adjacency map, and performs breadth-first traversal to the specified depth with a visited-node set. The result is formatted as `Final Answer: [...]` and scored by the original GraphWalks parser/F1 implementation already in the repository. The implementation sees the prompt only; its own answer is generated **before** gold answers are retrieved for scoring. Rows with unrecognized structure remain parse failures. No fallback to ground truth is permitted.

The resulting artifact contains the per-task prompt SHA-256, source identifier, parse status, F1 for parsed tasks, graph sizes and requested depth. It contains **no original prompts, prediction text, or gold node IDs**. Full-cohort F1 is withheld if any source prompt cannot be parsed; the scored-subset mean is labeled diagnostic.

## Why this control matters

A graph is an algorithmically tractable structure. A deterministic BFS is an expected structural control for a task asking for BFS; the result calibrates the benchmark's **graph extraction and parsing** dimensions, not a frontier model's long-context language understanding. A high control score must not be presented as model reproduction or as evidence that a provider's reported score was misstated. It also does not provide an equivalent resource profile or compute setting to a language model.

This space already has a relevant [FalkorDB/GraphWalks](https://github.com/FalkorDB/GraphWalks) graph-database/LLM proxy. Our control is an intentionally smaller, independent source-integrity check, not a competing API proxy. The original [OpenAI GraphWalks dataset](https://huggingface.co/datasets/openai/graphwalks) also records a February 2026 correction to BFS instructions and some parent-node ground truths; this source revision must be kept explicit.

## Reproduce independently

From the repository root with the optional `[graphwalks]` dependencies installed:

```bash
python scripts/graphwalks_data_audit.py \
  --revision be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7 \
  --sha256 537879431c72a42e3b500f80efc3047e7facb90390b6063d33679b4320985911 \
  --size-bytes 296903814 \
  --retain-parquet \
  --out .runs/private/control-source

python scripts/graphwalks_algorithmic_control.py \
  --parquet .runs/private/control-source/graphwalks_256k_to_1mil.parquet \
  --index .runs/private/control-source/graphwalks-bfs-reference-index.jsonl \
  --out .runs/graphwalks-algorithmic-control.json
```

The separate [GraphWalks algorithmic control GitHub Actions workflow](https://github.com/fraware/model-claim-replay/actions/workflows/graphwalks-algorithmic-control.yml) runs the same source-bound evaluation without any private credentials and uploads only the score-only JSON artifact. The [successful 21 November 2026 workflow](https://github.com/fraware/model-claim-replay/actions/runs/44884895995) reported 200/200 tasks parsed, zero failures, and **full-cohort F1 = 1.0**. The downloadable artifact was independently inspected: it contains 200 unique task IDs, 100 tasks per source-length group, all individual F1 values equal to 1.0, and no raw prompts, predictions or reference answer lists. The committed [task-level JSON receipt](../website/graphwalks-control.json) has SHA-256 `627be857ef90db4fe9ff3363f810c313b8454ee8ab0d5dfb2383825ec204bc0b`.

The first source-data run returned **0/200 parsed**, because the parser only recognized the initial BFS operation wording. The parser was extended to the public benchmark's February 2026 exact-depth wording and rerun on the same pinned data, yielding 200/200. This transparent correction was based on prompt syntax, not reference answers. The corrected parser was independently tested and retained as versioned code. **A control that solves explicit BFS tasks is not a performance claim about a language model.**
