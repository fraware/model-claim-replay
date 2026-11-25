# Roadmap

[Documentation home](README.md)

## Current implementation

The pre-release CLI supports portable text evaluation, offline fixtures, Inspect log import and paired comparisons, local hash checking and report generation. The website exposes the pinned public GraphWalks audit, Gemini input feasibility and one real OpenAI diagnostic. A separate [16-task OpenAI campaign](OPENAI_CAMPAIGN.md#observed-results) completed eight generations and recorded conditional F1 0.875, with eight context exclusions. Seven disclosed scores were independently recomputed; one malformed answer was withheld. The offline campaign journal verifier is implemented.

## Release candidate

- The original campaign ZIP is retained in Git; its digest, observed outcomes and seven disclosed-score cross-checks are documented.
- Review all user-facing documentation and install paths; collect five independent developer attempts.
- Obtain external score review; explicitly record any inaccessible evidence.
- Complete the [release acceptance gates](RELEASE_ACCEPTANCE.md), then publish the release candidate.

## Subsequent work

Integrate additional official harnesses where source access, licensing, scorer compatibility and budget permit. Expand claim-specific recipes, explicit protocol comparison and provenance review. Develop clearer disagreement diagnostics and permission-aware evidence exchange. Community reruns should retain independent identities and immutable results.

The long-term goal is a practical model-launch companion that connects a named public claim to inspectable experimental evidence. No publisher reproduction, support for arbitrary evaluators, or external adoption is asserted before validation.
