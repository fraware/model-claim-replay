# Development

[Documentation home](README.md)

Use Python 3.10 or newer. Start in a clean virtual environment with the repository checked out.

```bash
python -m venv .venv
```

Activate it with `source .venv/bin/activate` on POSIX or `.venv\\Scripts\\Activate.ps1` in PowerShell, then:

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
python scripts/visual_smoke.py --output-dir .runs/previews
python scripts/check_browser.py
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
