# Roadmap

[Documentation home](README.md)

## Current implementation

The pre-release CLI supports portable text evaluation, offline fixtures, Inspect log import and paired comparisons, local hash checking and report generation. The website exposes the pinned public GraphWalks audit, Gemini input feasibility and one real OpenAI diagnostic. A separate 16-task OpenAI campaign has completed preflight; the [execution record](https://github.com/fraware/model-claim-replay/actions/runs/45414635584) is authoritative for run status. The offline campaign journal verifier is implemented.

## Release candidate

- Verify and preserve the original campaign outcomes, including exclusions and incomplete requests.
- Review all user-facing documentation and install paths; collect five independent developer attempts.
- Obtain external score review; explicitly record any inaccessible evidence.
- Complete the [release acceptance gates](RELEASE_ACCEPTANCE.md), then publish the release candidate.

## Subsequent work

Integrate additional official harnesses where source access, licensing, scorer compatibility and budget permit. Expand claim-specific recipes, explicit protocol comparison and provenance review. Develop clearer disagreement diagnostics and permission-aware evidence exchange. Community reruns should retain independent identities and immutable results.

The long-term goal is a practical model-launch companion that connects a named public claim to inspectable experimental evidence. No publisher reproduction, support for arbitrary evaluators, or external adoption is asserted before validation.
