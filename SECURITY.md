# Security policy

Model Claim Replay is pre-release. Report security issues affecting the current main revision, including credential leakage, unintended paid requests, unsafe report rendering, private artifact disclosure or misleading verification behavior.

Use the repository's [private vulnerability reporting page](https://github.com/fraware/model-claim-replay/security/advisories/new) if available. If private reporting is unavailable, contact the maintainer via their GitHub profile for a private channel; do not publish sensitive exploit details or credentials in a public issue.

## Trust boundaries

- Treat imported logs, model answers, benchmark files and evidence bundles as untrusted data.
- Never commit API keys, environment files, raw private responses or proprietary task data.
- Store keys in the local environment or repository Actions secrets. Do not include them in screenshots, reports or feedback.
- A passing SHA-256 check establishes local commitment consistency, not authenticated provider execution.
- Paid model calls require explicit approval. Never retry a request with uncertain completion or accounting using the same authorization.
- Publish only authorized evidence fields; the full original response is excluded from public OpenAI artifacts.

For a suspected credential exposure, revoke the affected key with the provider promptly and review usage. Deleting a committed file does not remove it from Git history.

See [methodology](docs/METHODOLOGY.md) and the [automation inventory](docs/WORKFLOWS.md) for the project's evidence and execution boundaries.
