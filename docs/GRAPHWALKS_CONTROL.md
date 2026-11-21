# GraphWalks: a deterministic graph control

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

The separate [GraphWalks algorithmic control GitHub Actions workflow](https://github.com/fraware/model-claim-replay/actions/workflows/graphwalks-algorithmic-control.yml) runs the same source-bound evaluation without any private credentials and uploads only the score-only JSON artifact. Its numerical results should be consulted **only after** that workflow has passed and the uploaded report has been independently inspected.
