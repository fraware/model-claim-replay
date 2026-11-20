# Contributing

We welcome corrections, reproducibility improvements, and proposals for published claims with genuine developer relevance.

## Propose a claim

Include (1) an original publisher source, (2) the precise model and metric, (3) the dataset and scorer owner, (4) an exact executable protocol or a list of missing prerequisites, (5) benchmark license and access rights, and (6) a realistic cost estimate. Keep published scores separate from observed runs. Never add simulated vendor outputs as experimental results.

## Development expectations

Use Python 3.10+, stdlib wherever practical, type annotations, small units and focused tests. Run `python -m unittest discover -s tests -v` before proposing a change. Preserve the fixture distinction, avoid uploading API keys or proprietary benchmark data, and keep site pages compatible with static hosting. No generative model outputs are accepted as evidence without actual execution artifacts and a documented evaluation method.

MIT applies to code written here; external benchmarks carry their own licenses.
