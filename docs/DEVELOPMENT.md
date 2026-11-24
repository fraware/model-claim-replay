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

CI installs the built wheel in an unrelated directory, executes the offline demo and verifies its bundle. The website is static HTML/CSS/JS; browser tests cover desktop/mobile layouts, interactions and local file checks. GitHub Pages deployment is separate from browser test success.

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
