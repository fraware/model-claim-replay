# Contributing

We welcome corrections, reproducibility improvements and new source-linked claim investigations. Start with the [documentation index](docs/README.md) and [development guide](docs/DEVELOPMENT.md).

## Report a problem

Open a [GitHub issue](https://github.com/fraware/model-claim-replay/issues/new) with the revision, operating system, Python version, command, expected behavior and observed behavior. Include a minimal synthetic fixture when possible. Do not include API keys, private evaluation data, full provider responses or sensitive logs.

For installation or onboarding feedback, use the [developer replay form](https://github.com/fraware/model-claim-replay/issues/new?template=developer-replay-feedback.yml). Failed attempts and negative feedback are valuable. Security issues follow [SECURITY.md](SECURITY.md).

## Propose a claim

Include the original publisher statement, exact model and metric, benchmark owner and license, dataset/harness revision, scorer and judge settings, known reproduction blockers, and expected resource needs. Explain the intended comparison and population. A proxy experiment needs a distinct label. No synthetic or mock result is accepted as observed model performance.

## Submit a change

Fork or branch from main. Keep the change focused and include tests that exercise both the intended behavior and relevant failure cases. Run the offline regression suite described in [development](docs/DEVELOPMENT.md). Update the corresponding guide when changing a command, schema or trust boundary. Use the pull-request template to identify evidence and billing implications.

Preserve historical artifacts byte-for-byte; publish corrections as new derived records. Changes to source selection, protocol, paid authorization, publication policy or scoring need explicit review. Do not trigger paid experiments for routine CI.

Code contributions are covered by the repository's [MIT license](LICENSE). External benchmarks and evaluation data retain their original terms.
