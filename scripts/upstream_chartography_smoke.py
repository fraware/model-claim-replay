"""Exercise the pinned upstream Chartography task and inspect its actual .eval log.

This integration check uses only the two upstream *dummy* charts and Inspect's
mock model for both generation and grading. It never calls a provider, obtains
private benchmark data, or estimates frontier-model performance.
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from model_claim_replay.inspect_evidence import import_inspect_bundle, verify_inspect_bundle


UPSTREAM_SHA = "3f1bf837232d3918c2cc35c6e2418c9e70d2a57b"
ROOT = Path(__file__).resolve().parents[1]
CLAIM = ROOT / "claims" / "claude-fable-5-2-chartography.json"


def run_upstream_smoke(upstream: Path) -> None:
    """Run and import an actual official-harness log, rejecting unexpected results."""
    upstream = upstream.resolve(strict=True)
    if not (upstream / "src/chartography/task.py").is_file():
        raise RuntimeError("Pinned upstream checkout is missing the official Chartography task")

    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=upstream, capture_output=True,
        text=True, check=True, timeout=20,
    ).stdout.strip()
    if revision != UPSTREAM_SHA:
        raise RuntimeError(f"Unexpected upstream revision {revision}; expected {UPSTREAM_SHA}")

    with tempfile.TemporaryDirectory(prefix="mcr-upstream-smoke-") as temp:
        temp_dir = Path(temp)
        log_dir = temp_dir / "logs"
        command = [
            "inspect", "eval", "src/chartography/task.py",
            "--model", "mockllm/model", "-T", "limit=2",
            "-T", "judge_model=mockllm/model", "--log-dir", str(log_dir),
            "--max-connections", "1", "--display", "none",
        ]
        # The subprocess executes upstream code, isolated in a clean CI job.
        # In local use, inspect the pinned external code before executing it.
        subprocess.run(command, cwd=upstream, check=True, timeout=300)
        logs = sorted(log_dir.glob("*.eval"))
        if len(logs) != 1:
            raise RuntimeError(f"Expected one upstream Inspect log; found {len(logs)}")

        evidence_dir = temp_dir / "evidence"
        imported = import_inspect_bundle(CLAIM, logs[0], evidence_dir)
        verified = verify_inspect_bundle(CLAIM, evidence_dir, source_log=logs[0])
        if imported["attempted"] != 2 or imported["distinct_tasks"] != 2:
            raise RuntimeError("Official dummy task count is unexpected")
        if verified["comparison_status"] != "not_comparable":
            raise RuntimeError("The two-task mock smoke run must never be claim-comparable")
        if verified["source_log_checked"] is not True:
            raise RuntimeError("The original upstream log was not checked")
        if verified["source_log_sha256"] != imported.get("source_log_sha256", verified["source_log_sha256"]):
            raise RuntimeError("Source log hash mismatch")
        print(
            "Upstream Chartography smoke passed: 2 dummy tasks, "
            f"scored={verified['assessed']}, unscored={verified['unscored']}, "
            "publisher comparison blocked."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, type=Path)
    args = parser.parse_args()
    run_upstream_smoke(args.upstream)


if __name__ == "__main__":
    main()
