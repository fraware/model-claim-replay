"""Generate a complete, strictly synthetic claim-replay exercise offline.

The sample files are installed as package resources. Running this command
from an unrelated working directory uses exactly the same scoring and
verification path as a manually imported portable-text run. No credentials,
network connection, model generation or third-party dependency is involved.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from importlib import resources
from pathlib import Path
from typing import Any

from .core import (
    ReplayError, canonical_json, evaluate_records, load_claim, read_jsonl,
    task_data, verify_bundle,
)

_ASSETS = {
    "claim.json": "claim.json",
    "tasks.jsonl": "tasks.jsonl",
    "responses.jsonl": "responses.jsonl",
}

_GUIDE = """# Model Claim Replay — offline synthetic exercise

This directory was generated from packaged, deliberately artificial examples.
The 2/3 exact-match result tests the software workflow. It is not evidence
about a real AI model, a benchmark publisher, or external inference.

Open report.html in a browser to inspect the local report. report.json holds
the same verification summary in machine-readable form.

From this directory, independently rerun the integrity and scoring checks:

    claim-replay verify run --claim claim.json --tasks tasks.jsonl

You can also generate a second report without modifying the evidence:

    claim-replay report run --claim claim.json --tasks tasks.jsonl \
        --format html --output rerun-report.html

Files:
    claim.json       A source-labeled synthetic claim and task-data hash
    tasks.jsonl      Three predefined exact-match tasks and gold answers
    responses.jsonl  Three predefined responses (two correct, one incorrect)
    run/run.json     Manifest of local hashes, model label and import status
    run/results.jsonl  Imported observations
    report.json      Recomputed scoring and coverage
    report.html      Self-contained, offline HTML evidence report

All evaluation inputs are user-inspectable; no model API requests occur.
No third-party evaluation was run. SHA-256 validates local integrity,
not independent provenance or provider identity.
"""


def generate_offline_demo(output: Path) -> dict[str, Any]:
    """Produce a verified demo bundle, refusing an existing destination.

    Stage and validate the entire bundle before publishing it. The output
    directory is created exclusively, and preexisting output is preserved.
    """
    if output.exists() or output.is_symlink():
        raise ReplayError(f"Demo output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mcr-demo-", dir=output.parent) as scratch:
        stage = Path(scratch)
        package = resources.files("model_claim_replay")
        for destination, name in _ASSETS.items():
            try:
                data = package.joinpath("demo_assets", name).read_bytes()
            except (FileNotFoundError, OSError) as exc:
                raise ReplayError(f"Installed offline demo asset missing: {name}") from exc
            (stage / destination).write_bytes(data)

        claim_path, tasks_path = stage / "claim.json", stage / "tasks.jsonl"
        claim = load_claim(claim_path)
        tasks = task_data(claim, tasks_path)
        if claim["kind"] != "synthetic" or claim["id"] != "demo-text-exact-match":
            raise ReplayError("Offline demonstration is not a validated synthetic fixture")
        originals = read_jsonl(stage / "responses.jsonl")
        results = []
        for record in originals:
            if set(record) != {"id", "output"} or not isinstance(record["output"], str):
                raise ReplayError("Synthetic response fixture has an invalid record")
            results.append({"id": record["id"], "status": "ok", "output": record["output"]})

        summary = evaluate_records(
            claim, tasks, results, model="fixture-model", run_kind="imported",
        )
        if (summary["successes"], summary["failures"], summary["assessed"]) != (2, 1, 3):
            raise ReplayError("Packaged synthetic responses no longer match the expected fixture")
        if summary["comparison_status"] != "not_comparable":
            raise ReplayError("Synthetic test improperly claims publisher comparability")

        # Import locally to avoid introducing a parallel evidence or HTML format.
        from .cli import _report_page, save_run

        save_run(
            claim_path=claim_path, tasks_path=tasks_path, claim=claim,
            results=results, directory=stage / "run", model="fixture-model",
            run_kind="imported",
        )
        verified = verify_bundle(claim_path, tasks_path, stage / "run")
        if verified != summary:
            raise ReplayError("Generated bundle fails its independent scoring check")
        (stage / "report.json").write_bytes(canonical_json(verified) + b"\n")
        (stage / "report.html").write_text(
            _report_page(claim, verified), encoding="utf-8",
        )
        (stage / "README.md").write_text(_GUIDE, encoding="utf-8")

        # Creating the destination is exclusive on both POSIX and Windows.
        # Populate only after all fixture and report checks pass.
        try:
            output.mkdir(exist_ok=False)
        except FileExistsError as exc:
            raise ReplayError(f"Demo output already exists: {output}") from exc
        try:
            for child in stage.iterdir():
                os.replace(child, output / child.name)
        except BaseException:
            shutil.rmtree(output)
            raise
        return verified
