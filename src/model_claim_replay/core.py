"""Validation, deterministic scoring, and evidence-bundle integrity.

The package deliberately does not claim cryptographic origin authentication. SHA-256
binds each *self-reported* run to local artifacts; independent execution or signed
attestation is necessary to establish provenance beyond that local binding.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,100}$")


class ReplayError(ValueError):
    """Raised for invalid evidence or an unsupported claim protocol."""


def canonical_json(obj: Any) -> bytes:
    """Serialize a JSON value consistently for manifest content addressing."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(blob: bytes) -> str:
    """Return a lowercase hexadecimal SHA-256 digest."""
    return hashlib.sha256(blob).hexdigest()


def read_bytes(path: Path) -> bytes:
    """Read a bounded local artifact, rejecting unexpectedly large files."""
    if not path.is_file():
        raise ReplayError(f"Missing file: {path}")
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ReplayError(f"Artifact exceeds {MAX_ARTIFACT_BYTES} bytes: {path}")
    return path.read_bytes()


def read_json(path: Path) -> Any:
    """Load JSON, reporting parse failures as user-facing validation errors."""
    try:
        return json.loads(read_bytes(path))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReplayError(f"Invalid JSON in {path}: {exc}") from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL artifact with strict object and duplicate-ID checks."""
    try:
        lines = read_bytes(path).decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise ReplayError(f"Invalid UTF-8 in {path}") from exc
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReplayError(f"Invalid JSONL in {path} on line {number}: {exc}") from exc
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ReplayError(f"Line {number} in {path} must be an object with a string id")
        ident = item["id"]
        if not ID_PATTERN.fullmatch(ident) or ident in seen:
            raise ReplayError(f"Duplicate or invalid item id {ident!r} in {path}")
        seen.add(ident)
        records.append(item)
    if not records:
        raise ReplayError(f"No records in {path}")
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """Write deterministic JSONL, preserving each task's original order."""
    path.write_bytes(b"".join(canonical_json(item) + b"\n" for item in records))


def load_claim(path: Path) -> dict[str, Any]:
    """Validate v1 of the narrow claim format before any execution."""
    claim = read_json(path)
    if not isinstance(claim, dict) or claim.get("schema_version") != "1":
        raise ReplayError("Claim must be a JSON object with schema_version='1'")
    ident = claim.get("id")
    if not isinstance(ident, str) or not ID_PATTERN.fullmatch(ident):
        raise ReplayError("Claim id must be a lowercase, path-safe slug")
    if claim.get("kind") not in ("published", "synthetic"):
        raise ReplayError("Claim kind must be published or synthetic")
    for name in ("title", "model", "source", "benchmark", "protocol"):
        if not isinstance(claim.get(name), (str if name == "title" else dict)):
            raise ReplayError(f"Claim has invalid or missing {name}")
    for nested, key in (("model", "name"), ("benchmark", "name"), ("source", "url")):
        if not isinstance(claim[nested].get(key), str) or not claim[nested][key]:
            raise ReplayError(f"Claim is missing {nested}.{key}")
    if not claim["source"]["url"].startswith("https://"):
        raise ReplayError("Source URL must use HTTPS")
    score = claim.get("reported_score")
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(score) or not 0 <= score <= 1:
        raise ReplayError("reported_score must be a finite fraction in [0, 1]")
    benchmark = claim["benchmark"]
    expected = benchmark.get("expected_tasks")
    if not isinstance(expected, int) or isinstance(expected, bool) or expected < 1:
        raise ReplayError("benchmark.expected_tasks must be a positive integer")
    digest = benchmark.get("sha256")
    if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise ReplayError("benchmark.sha256 must be a lowercase SHA-256 hex string or null")
    protocol = claim["protocol"]
    if protocol.get("mode") not in ("portable-text", "external"):
        raise ReplayError("protocol.mode must be portable-text or external")
    if protocol["mode"] == "portable-text":
        if protocol.get("scoring") != "exact-match" or protocol.get("normalization") not in ("none", "strip", "strip-casefold"):
            raise ReplayError("Portable text supports exact-match and documented normalization only")
    return claim


def task_data(claim: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    """Validate canonical task bytes and their expected cardinality."""
    digest = claim["benchmark"].get("sha256")
    if digest is None:
        raise ReplayError("This claim has no pinned dataset digest; reproduction blocked")
    if sha256_bytes(read_bytes(path)) != digest:
        raise ReplayError("Task dataset SHA-256 does not match the claim manifest")
    tasks = read_jsonl(path)
    if len(tasks) != claim["benchmark"]["expected_tasks"]:
        raise ReplayError("Dataset task count differs from the claim manifest")
    if claim["protocol"]["mode"] != "portable-text":
        raise ReplayError("External harness claim is not executable by the portable runner")
    for task in tasks:
        if not isinstance(task.get("prompt"), str) or not isinstance(task.get("expected"), str):
            raise ReplayError("Every portable task needs a string prompt and expected answer")
    return tasks


def normalized(value: str, mode: str) -> str:
    """Normalize answers exactly as specified in the claim."""
    if mode == "strip":
        return value.strip()
    if mode == "strip-casefold":
        return value.strip().casefold()
    return value


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    """95% Wilson score interval; descriptive only, under an i.i.d. Bernoulli model."""
    if not total:
        return None
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return max(0.0, center - half), min(1.0, center + half)


def evaluate_records(claim: dict[str, Any], tasks: list[dict[str, Any]], results: list[dict[str, Any]], *, model: str, run_kind: str) -> dict[str, Any]:
    """Recompute scores and enforce the claim-comparability gate.

    An imported result or a subset run is never labeled a full reproduction.
    Even a full portable run is self-reported, without independently trusted
    execution or assurance of a hosted model's immutable identity.
    """
    by_id = {item["id"]: item for item in results}
    task_ids = {task["id"] for task in tasks}
    if len(by_id) != len(results) or not set(by_id).issubset(task_ids):
        raise ReplayError("Results contain duplicate or unknown task IDs")
    good = failures = errors = 0
    scored: list[dict[str, Any]] = []
    mode = claim["protocol"]["normalization"]
    for task in tasks:
        result = by_id.get(task["id"])
        if result is None:
            continue
        if result.get("status") == "error":
            errors += 1
            scored.append({"id": task["id"], "status": "error"})
            continue
        if result.get("status") != "ok" or not isinstance(result.get("output"), str):
            raise ReplayError(f"Invalid status or output for task {task['id']}")
        success = normalized(result["output"], mode) == normalized(task["expected"], mode)
        good += int(success)
        failures += int(not success)
        scored.append({"id": task["id"], "status": "pass" if success else "fail"})
    assessed = good + failures
    completed = len(results) == len(tasks) and errors == 0
    eligible = (
        completed
        and claim["kind"] == "published"
        and claim["protocol"]["mode"] == "portable-text"
        and model == claim["model"]["name"]
        and run_kind == "api"
    )
    return {
        "claim_id": claim["id"],
        "model": model,
        "run_kind": run_kind,
        "kind": claim["kind"],
        "reported_score": claim["reported_score"],
        "observed_score": good / assessed if assessed else None,
        "wilson_95": wilson_interval(good, assessed),
        "successes": good,
        "failures": failures,
        "errors": errors,
        "assessed": assessed,
        "attempted": len(results),
        "total_tasks": len(tasks),
        "comparison_status": "candidate_protocol_match_self_reported" if eligible else "not_comparable",
        "comparison_explanation": (
            "Full dataset, declared portable scoring, model label, and local API run match. "
            "Provider execution and model identity have not been independently attested."
            if eligible else
            "Synthetic, imported, incomplete, model-mismatched, or non-portable runs do not establish the published claim."
        ),
        "task_results": scored,
    }


def verify_bundle(claim_path: Path, tasks_path: Path, run_dir: Path) -> dict[str, Any]:
    """Validate run digests and recompute the score from pinned task ground truth."""
    claim = load_claim(claim_path)
    tasks = task_data(claim, tasks_path)
    metadata = read_json(run_dir / "run.json")
    if not isinstance(metadata, dict) or metadata.get("schema_version") != "1":
        raise ReplayError("Invalid run metadata schema")
    if metadata.get("claim_id") != claim["id"]:
        raise ReplayError("Run claims a different claim ID")
    if metadata.get("manifest_sha256") != sha256_bytes(read_bytes(claim_path)):
        raise ReplayError("Run's claim manifest digest does not match")
    if metadata.get("tasks_sha256") != sha256_bytes(read_bytes(tasks_path)):
        raise ReplayError("Run's dataset digest does not match")
    results_path = run_dir / "results.jsonl"
    if metadata.get("results_sha256") != sha256_bytes(read_bytes(results_path)):
        raise ReplayError("Run results were modified after recording")
    results = read_jsonl(results_path)
    model = metadata.get("model")
    run_kind = metadata.get("run_kind")
    if not isinstance(model, str) or not model or run_kind not in ("api", "imported"):
        raise ReplayError("Run metadata has invalid model or execution type")
    return evaluate_records(claim, tasks, results, model=model, run_kind=run_kind)
