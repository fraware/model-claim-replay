# Development

[Documentation home](README.md)

Use Python 3.10 or newer. Start in a clean virtual environment with the repository checked out.

```bash
python -m venv .venv
```

Activate it with `source .venv/bin/activate` on POSIX or `.venv\Scripts\Activate.ps1` in PowerShell, then:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

The default regression suite uses local fixtures and mocked transports. Do not supply live model credentials for these tests.

## Optional integration checks

```bash
python -m pip install -e '.[inspect,graphwalks]'
python -m unittest discover -s tests -p 'test_inspect_runtime.py' -v
python -m unittest discover -s tests -p 'test_graphwalks_runtime.py' -v
```

CI also executes the pinned Chartography upstream harness on public dummy tasks with a mock model and judge. Its scores are synthetic integration evidence.

## Browser and packaging

```bash
python -m pip install playwright
python -m playwright install chromium
python scripts/visual_smoke.py --site website --out .runs/previews
python scripts/check_browser.py --site website
python -m pip wheel . --no-deps --wheel-dir .runs/wheels
```

CI installs the built wheel in an unrelated directory, executes the offline demo and verifies its bundle. The website is static HTML/CSS/JS; browser tests cover desktop/mobile layouts, interactions and local file checks. GitHub Pages deployment is separate from browser test success. Its read-only post-deployment job compares the actual public HTML, scripts, styles and evidence assets byte-for-byte with the checkout, then opens the three public pages in Chromium at desktop and mobile widths. The `production-smoke` artifact retains asset hashes and screenshots. This is a maintainer-run production check, not independent user testing.

## Repository layout

| Path | Responsibility |
|---|---|
| `src/model_claim_replay/` | Installable package, CLI, adapters, evidence validation, scoring. |
| `claims/` | Source-linked claim manifests. |
| `examples/` | Small synthetic fixtures. |
| `evidence/` | Original public evidence archives, source commitments and authorization records. |
| `scripts/` | Source audit, provider-specific experiments, website and reviewer tools. |
| `tests/` | Offline regressions and optional integrations. |
| `website/` | Static explorer and browser verifier. |
| `.github/workflows/` | CI, publication, provider probes and separately authorized experiments. |

The [automation inventory](WORKFLOWS.md) classifies each workflow. Do not change a paid trigger, historical authorization, original artifact digest or experiment protocol as part of a documentation edit. Keep private output in ignored local directories. Review the [security policy](../SECURITY.md) before uploading evidence.

## Dependency maintenance

The core CLI has no third-party runtime dependencies. The Inspect, GraphWalks and browser integrations resolve optional packages at installation time. The CI dependency-audit job installs the optional integrations together in a fresh Python 3.12 environment, checks declared requirements with `pip check`, records the resolved versions, and audits those exact third-party versions with [pip-audit](https://github.com/pypa/pip-audit). The auditor runs in a separate environment, and no model credentials are used. The local unpublished project itself is excluded from the third-party advisory query; its version is still recorded.

Known advisories and audit failures fail the job; no automatic fixes or ignored advisory IDs are configured. Download the `dependency-audit` artifact for the resolved package list and JSON findings. This is a point-in-time advisory scan on Linux/Python 3.12, not a hash-locked research environment, a source-code security review, an audit of every historical environment or a check of browser binaries, build-only dependencies and OS libraries. The separately pinned upstream Chartography checkout retains its own dependency graph. Record and review exact environment versions for research runs.

Weekly Dependabot proposals cover Python manifests and Actions references. Review dependency changes against CI, supported Python versions and historical paid execution controls. Do not auto-merge upgrades. Existing Actions release tracks are version references, not immutable commit pins.

## Release candidate packages

The cross-platform CI job builds a source distribution and a wheel from that distribution on Linux, macOS and Windows. Each wheel is installed into a clean environment with `--no-index --no-deps`; the actual executable creates and verifies the synthetic demonstration. The artifact includes both packages and a SHA-256 receipt with the tested source revision, Python version, platform and automated timing.

This is an automated maintainer check, not one of the five independent developer sessions. The artifacts are release candidates, not a published tag or PyPI release. Builds still resolve the build frontend/backend; byte-identical rebuilds are not claimed. The historical evidence verification command is a separate repository-checkout operation, not bundled into the base wheel.

Git attributes enforce canonical LF checkout for text evidence and fixtures on every platform. ZIP archives are binary; their bytes are never normalized. Do not refresh pinned digests to accommodate platform line-ending conversion.

The source distribution is a complete public repository snapshot: it includes the tracked documentation, workflows, tests, fixtures, verification scripts and explicitly allowlisted historical evidence. The release job verifies every tracked file's exact bytes against the sdist, rejects unexpected untracked archive members except generated packaging metadata, and executes the archived evidence verifier from the extracted snapshot using the installed wheel. The wheel remains limited to package code and resources; it does not contain the reference-answer archive. The source snapshot contains public benchmark reference answers, which must remain separate from model prompts. No private output or credentials should be placed in the tracked tree.
