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
