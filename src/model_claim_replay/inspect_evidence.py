"""Strict, privacy-conscious import of original Inspect AI evaluation logs.

This module intentionally consumes the official Inspect Log API instead of parsing
`.eval` archives or reimplementing a benchmark's judge. A verified *import* is
not an independent reproduction or an attestation of the model provider.

Only task identifiers' keyed digests, epoch numbers, binary scores, and run
configuration excerpts leave the source log. The raw log, charts, targets, prompts,
model responses, and judge rationales are never copied into an evidence bundle.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import math
import os
import random
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from .core import ReplayError, canonical_json, load_claim, read_bytes, read_jsonl, sha256_bytes, write_jsonl
from .content_fingerprint import sample_content_sha256

MAX_INSPECT_LOG_BYTES = 1024 * 1024 * 1024
SCORER_NAME = "golden_answer_scorer"
SCORE_KEY = "accuracy"
SCORE_AGGREGATOR = "mean"


def hash_log_file(path: Path) -> str:
    """Hash a local, bounded Inspect log without loading image-bearing logs in RAM."""
    if not path.is_file():
        raise ReplayError(f"Inspect log is not a regular file: {path}")
    if path.stat().st_size > MAX_INSPECT_LOG_BYTES:
        raise ReplayError("Inspect log exceeds the 1 GiB local import limit")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_inspect_log(path: Path) -> Any:
    """Read Inspect `.eval` or `.json` through its public Python API.

    Inspect is optional for users who only verify a previously exported bundle.
    """
    hash_log_file(path)  # Fail before parsing an oversized/unexpected path.
    try:
        from inspect_ai.log import read_eval_log
    except ImportError as exc:
        raise ReplayError("Inspect AI is required for import: pip install 'model-claim-replay[inspect]'") from exc
    try:
        return read_eval_log(str(path), resolve_attachments=False)
    except Exception as exc:
        # Do not echo original exceptions; parser errors can include private input.
        raise ReplayError(f"Inspect could not parse the evaluation log ({type(exc).__name__})") from exc


def _as_dict(value: Any) -> dict[str, Any]:
    """Convert Pydantic score mappings without assuming a specific log serializer."""
    if isinstance(value, dict):
        return value
    return {}


def _score_value(sample: Any) -> tuple[str, int | None]:
    """Return pass/fail/unscored/error for the named Chartography scorer only."""
    if getattr(sample, "error", None) is not None:
        return "error", None
    scores = _as_dict(getattr(sample, "scores", None))
    if SCORER_NAME not in scores:
        return "unscored", None
    raw = getattr(scores[SCORER_NAME], "value", None)
    if not isinstance(raw, dict) or set(raw) != {SCORE_KEY}:
        raise ReplayError("Expected a named Chartography scorer with one accuracy value")
    value = raw[SCORE_KEY]
    if isinstance(value, float) and math.isnan(value):
        return "unscored", None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value not in (0, 1):
        raise ReplayError("Chartography accuracy score must be exactly 0, 1, or NaN for unscored")
    outcome = "pass" if value == 1 else "fail"
    metadata = _as_dict(getattr(scores[SCORER_NAME], "metadata", None))
    label = metadata.get("result")
    if label is not None and label != outcome:
        raise ReplayError("Chartography scorer result metadata contradicts its numeric score")
    return outcome, int(value)


def _sample_key(sample_id: str | int) -> str:
    """Generate a stable opaque task label without publishing benchmark content.

    A digest is pseudonymization, not a privacy guarantee against dictionary attacks.
    """
    digest = hashlib.sha256(b"mcr-inspect-id-v1\0" + canonical_json(sample_id)).hexdigest()
    return digest[:40]


def _header_metric(log: Any) -> float | None:
    """Extract the benchmark's *named* mean score from Inspect aggregate results."""
    results = getattr(log, "results", None)
    if results is None:
        return None
    matches = [s for s in (getattr(results, "scores", None) or [])
               if getattr(s, "scorer", None) == SCORER_NAME
               and getattr(s, "name", None) == SCORE_KEY
               and getattr(s, "reducer", None) in (None, SCORE_AGGREGATOR)]
    if not matches:
        return None
    if len(matches) != 1:
        raise ReplayError("Ambiguous Inspect aggregate: more than one named accuracy/mean score")
    metric = _as_dict(getattr(matches[0], "metrics", None)).get(SCORE_AGGREGATOR)
    value = getattr(metric, "value", None)
    # Inspect can emit NaN for a run with no scored task-epochs (for example,
    # a mock judge that never produces a parseable verdict). Preserve this as
    # a missing aggregate; never turn it into a zero-accuracy model result.
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ReplayError("Inspect aggregate accuracy/mean is invalid")
    return float(value)


def extract_inspect_records(log: Any, claim: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate an Inspect run and extract non-sensitive scoring-only evidence.

    Content and source-protocol verification are distinct. Log status success is
    required, while incomplete, mismatched, or subset runs remain importable with
    explicit blockers and never count as confirmation of the publisher's claim.
    """
    if claim["protocol"]["mode"] != "external" or claim["benchmark"]["name"] != "Chartography":
        raise ReplayError("This Inspect importer supports only external Chartography claims")
    if getattr(log, "status", None) != "success":
        raise ReplayError("Inspect log status is not success; a failed run cannot be imported")
    eval_spec = getattr(log, "eval", None)
    if eval_spec is None or getattr(eval_spec, "task", None) != "chartography":
        raise ReplayError("Inspect log was not produced by the chartography task")
    model = getattr(eval_spec, "model", None)
    if not isinstance(model, str) or not model:
        raise ReplayError("Inspect log has no recorded model name")
    sample_objects = getattr(log, "samples", None)
    if not isinstance(sample_objects, list) or not sample_objects:
        raise ReplayError("Inspect log contains no samples; import requires detailed sample logging")
    if len(sample_objects) > 100_000:
        raise ReplayError("Inspect log has an unsupported sample count")

    records: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for sample in sample_objects:
        raw_id = getattr(sample, "id", None)
        if isinstance(raw_id, bool) or not isinstance(raw_id, (str, int)) or not str(raw_id):
            raise ReplayError("Inspect sample lacks a valid string or integer ID")
        epoch = getattr(sample, "epoch", None)
        if isinstance(epoch, bool) or not isinstance(epoch, int) or not 1 <= epoch <= 10_000:
            raise ReplayError("Inspect sample epoch must be a positive integer")
        task_key = _sample_key(raw_id)
        if (task_key, epoch) in seen:
            raise ReplayError("Duplicate Inspect task/epoch pair")
        seen.add((task_key, epoch))
        outcome, score = _score_value(sample)
        record: dict[str, Any] = {
            "id": f"{task_key}-e{epoch}", "task_key": task_key,
            "epoch": epoch, "status": outcome,
        }
        if score is not None:
            record["score"] = score
        content_digest = sample_content_sha256(sample)
        if content_digest is not None:
            record["content_sha256"] = content_digest
        records.append(record)
    records.sort(key=lambda r: (r["task_key"], r["epoch"]))

    config = getattr(eval_spec, "config", None)
    task_args = _as_dict(getattr(eval_spec, "task_args", None))
    # Explicit task arguments; preserve names but never serialize arbitrary data.
    judge = task_args.get("judge_model")
    hf_repo = task_args.get("hf_repo")
    split = task_args.get("split")
    revision = getattr(eval_spec, "revision", None)
    revision_commit = getattr(revision, "commit", None)
    revision_dirty = getattr(revision, "dirty", None)
    packages = _as_dict(getattr(eval_spec, "packages", None))
    epochs = getattr(config, "epochs", None)
    if epochs is not None and (isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1):
        raise ReplayError("Inspect log has invalid requested epoch count")
    total = getattr(getattr(log, "results", None), "total_samples", None)
    completed = getattr(getattr(log, "results", None), "completed_samples", None)
    header_score = _header_metric(log)
    for field, value in (("total_samples", total), ("completed_samples", completed)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ReplayError(f"Inspect log has invalid {field}")
    if total is not None and total < len(records):
        raise ReplayError("Inspect log has more sample records than the reported total")
    header = {
        "task": "chartography",
        "model": model,
        "judge_model": judge if isinstance(judge, str) and judge else None,
        "dataset_repo": hf_repo if isinstance(hf_repo, str) and hf_repo else None,
        "dataset_split": split if isinstance(split, str) and split else None,
        "requested_epochs": epochs,
        "harness_revision": revision_commit if isinstance(revision_commit, str) else None,
        "harness_dirty": revision_dirty if isinstance(revision_dirty, bool) else None,
        "inspect_version": packages.get("inspect_ai") if isinstance(packages.get("inspect_ai"), str) else None,
        "logged_total_samples": total,
        "logged_completed_samples": completed,
        "logged_mean": header_score,
    }
    return records, header


def _score_summary(claim: dict[str, Any], records: list[dict[str, Any]], header: dict[str, Any]) -> dict[str, Any]:
    """Recompute the score, task coverage and conservative comparison blockers."""
    seen: set[tuple[str, int]] = set()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        ident = r.get("id")
        task_key, epoch = r.get("task_key"), r.get("epoch")
        if (not isinstance(ident, str) or not isinstance(task_key, str) or len(task_key) != 40
                or not all(c in "0123456789abcdef" for c in task_key)):
            raise ReplayError("Invalid task digest or record identifier")
        if isinstance(epoch, bool) or not isinstance(epoch, int) or not 1 <= epoch <= 10_000:
            raise ReplayError("Invalid epoch in imported evidence")
        if ident != f"{task_key}-e{epoch}" or (task_key, epoch) in seen:
            raise ReplayError("Duplicate or inconsistent imported task/epoch record")
        seen.add((task_key, epoch))
        status = r.get("status")
        if status not in ("pass", "fail", "error", "unscored"):
            raise ReplayError("Invalid imported score status")
        if status in ("pass", "fail"):
            score = r.get("score")
            if isinstance(score, bool) or not isinstance(score, int) or score != int(status == "pass"):
                raise ReplayError("Imported score contradicts its status")
        elif "score" in r:
            raise ReplayError("Unscored and errored records cannot have a numeric score")
        content_digest = r.get("content_sha256")
        if content_digest is not None and (
            not isinstance(content_digest, str) or len(content_digest) != 64 or
            any(char not in "0123456789abcdef" for char in content_digest)
        ):
            raise ReplayError("Invalid sample-content SHA-256 fingerprint")
        grouped[task_key].append(r)

    content_fingerprinted = sum("content_sha256" in row for row in records)
    for task_rows in grouped.values():
        content_versions = {row["content_sha256"] for row in task_rows
                            if "content_sha256" in row}
        if len(content_versions) > 1:
            raise ReplayError("Logged task content differs across repeated epochs")

    good = sum(r["status"] == "pass" for r in records)
    bad = sum(r["status"] == "fail" for r in records)
    errors = sum(r["status"] == "error" for r in records)
    unscored = sum(r["status"] == "unscored" for r in records)
    assessed = good + bad
    observed = good / assessed if assessed else None
    expected_tasks = claim["benchmark"]["expected_tasks"]
    expected_epochs = claim["protocol"].get("reference_epochs")
    if isinstance(expected_epochs, bool) or not isinstance(expected_epochs, int) or expected_epochs < 1:
        raise ReplayError("External manifest requires a positive protocol.reference_epochs")
    # A complete run must include exactly 1..K for each of the expected tasks.
    full_grid = (len(grouped) == expected_tasks and all(
        {r["epoch"] for r in rows} == set(range(1, expected_epochs + 1))
        for rows in grouped.values()
    ))
    all_scored = full_grid and errors == 0 and unscored == 0
    logged_mean = header.get("logged_mean")
    # Do not falsely equate partial-run means with the official metric, which
    # may use different denominators or reduction semantics.
    if all_scored and logged_mean is not None and observed is not None and abs(observed - logged_mean) > 1e-8:
        raise ReplayError("Recomputed task/epoch mean disagrees with Inspect's logged accuracy/mean")
    blockers = []
    if not full_grid:
        blockers.append("Incomplete 100-task × 10-epoch evidence grid or unexpected epoch numbering")
    if errors or unscored:
        blockers.append("At least one task/epoch is unscored or errored")
    if content_fingerprinted != len(records):
        blockers.append("Not all chart images and reference answers have byte-bound input fingerprints")
    if header.get("task") != "chartography":
        blockers.append("Logged task differs from official Chartography task")
    if header.get("model") != claim["model"]["name"]:
        blockers.append("Model identifier differs from the published model label, or aliases are unresolved")
    if header.get("judge_model") != claim["protocol"].get("reference_judge_model"):
        blockers.append("Judge model was not confirmed to match the benchmark reference")
    if header.get("dataset_repo") != claim["protocol"].get("reference_dataset_repo"):
        blockers.append("Dataset source differs or cannot be established from log metadata")
    if header.get("requested_epochs") != expected_epochs:
        blockers.append("Requested repeat/epoch count is missing or differs from the benchmark reference")
    if header.get("harness_revision") != claim["protocol"].get("reference_harness_commit") or header.get("harness_dirty") is True:
        blockers.append("Official harness revision or clean working tree cannot be confirmed")
    if header.get("logged_mean") is None:
        blockers.append("No original Inspect accuracy/mean aggregate in the source log")
    # Always block equivalence to Anthropic's 73.4% until its actual run config
    # and evaluator provenance are published and independently matched.
    blockers.append("Publisher's exact model, sampling, dataset and judge protocol is not verified")
    blockers.append("Source log and provider execution are self-reported, not authenticated")

    # Task-cluster bootstrap is descriptive only for the fixed benchmark tasks.
    cluster_ci: list[float] | None = None
    if all_scored and len(grouped) > 1:
        task_means = [sum(int(r["score"]) for r in rows) / len(rows) for rows in grouped.values()]
        rng = random.Random(20261120)
        n = len(task_means)
        draws = sorted(sum(task_means[rng.randrange(n)] for _ in range(n)) / n for _ in range(3000))
        cluster_ci = [draws[74], draws[2924]]  # 2.5% / 97.5%, zero-indexed, 3,000 draws.

    return {
        "schema_version": "inspect-v1",
        "claim_id": claim["id"],
        "kind": claim["kind"],
        "model": header.get("model"),
        "run_kind": "inspect_import_self_reported",
        "reported_score": claim["reported_score"],
        "observed_score": observed,
        "observed_denominator": assessed,
        "task_cluster_bootstrap_95": cluster_ci,
        "task_cluster_bootstrap_note": (
            "Exploratory task-resampling interval conditional on this curated benchmark, "
            "not a population-confidence guarantee or a comparison test."
        ),
        "successes": good, "failures": bad, "errors": errors, "unscored": unscored,
        "assessed": assessed, "attempted": len(records),
        "content_fingerprinted": content_fingerprinted,
        "distinct_tasks": len(grouped), "total_tasks": expected_tasks,
        "expected_epochs": expected_epochs, "coverage_complete": full_grid,
        "reference_protocol_flags": {
            "judge_recorded": header.get("judge_model"),
            "dataset_recorded": header.get("dataset_repo"),
            "harness_revision_recorded": header.get("harness_revision"),
            "inspect_version_recorded": header.get("inspect_version"),
            "logged_mean": logged_mean,
        },
        "comparison_status": "not_comparable",
        "comparison_explanation": "This audit imports scores from a local Inspect log. The publisher's headline protocol has not been established, and model/provider execution is not independently authenticated.",
        "comparison_blockers": blockers,
        "task_results": [{"id": r["task_key"], "epoch": r["epoch"], "status": r["status"]} for r in records],
    }


def import_inspect_bundle(claim_path: Path, log_path: Path, out: Path, *, log: Any | None = None) -> dict[str, Any]:
    """Import and validate an Inspect log, writing an atomic scoring-only bundle."""
    claim = load_claim(claim_path)
    source_hash = hash_log_file(log_path)
    log_object = read_inspect_log(log_path) if log is None else log
    records, header = extract_inspect_records(log_object, claim)
    summary = _score_summary(claim, records, header)
    if out.exists():
        raise ReplayError(f"Output path already exists: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=".mcr-inspect-", dir=out.parent))
    try:
        write_jsonl(staged / "results.jsonl", records)
        metadata = {
            "schema_version": "inspect-v1", "claim_id": claim["id"],
            "manifest_sha256": sha256_bytes(read_bytes(claim_path)),
            "results_sha256": sha256_bytes(read_bytes(staged / "results.jsonl")),
            "source_log_sha256": source_hash,
            "source_log_filename": log_path.name,
            "source_log_bytes": log_path.stat().st_size,
            "run_kind": "inspect_import_self_reported",
            "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "inspect_header": header,
            "provenance": "self_reported_unattested",
            "content_policy": "score_metadata_only_no_raw_prompts_images_targets_or_model_outputs",
        }
        (staged / "run.json").write_bytes(canonical_json(metadata) + b"\n")
        os.rename(staged, out)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    return summary


def verify_inspect_bundle(claim_path: Path, run_dir: Path, *, source_log: Path | None = None) -> dict[str, Any]:
    """Verify local artifact hashes and independently recompute imported scores.

    Source log hash checking is optional, explicit, and does not authenticate
    provider execution. An unchanged run.json alone only attests to local bytes.
    """
    claim = load_claim(claim_path)
    metadata_path = run_dir / "run.json"
    metadata_bytes = read_bytes(metadata_path)
    try:
        metadata = json.loads(metadata_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ReplayError("Inspect bundle run.json is not valid JSON") from exc
    if not isinstance(metadata, dict) or metadata.get("schema_version") != "inspect-v1":
        raise ReplayError("Not an Inspect evidence bundle")
    if metadata.get("claim_id") != claim["id"] or metadata.get("manifest_sha256") != sha256_bytes(read_bytes(claim_path)):
        raise ReplayError("Inspect evidence is bound to a different claim manifest")
    if metadata.get("run_kind") != "inspect_import_self_reported":
        raise ReplayError("Unsupported Inspect evidence provenance")
    results_path = run_dir / "results.jsonl"
    if metadata.get("results_sha256") != sha256_bytes(read_bytes(results_path)):
        raise ReplayError("Inspect scores changed since bundle creation")
    raw_hash = metadata.get("source_log_sha256")
    if not isinstance(raw_hash, str) or len(raw_hash) != 64 or any(c not in '0123456789abcdef' for c in raw_hash):
        raise ReplayError("Source log has an invalid SHA-256 commitment")
    if source_log is not None and hash_log_file(source_log) != raw_hash:
        raise ReplayError("Source Inspect log no longer matches recorded SHA-256")
    header = metadata.get("inspect_header")
    if not isinstance(header, dict):
        raise ReplayError("Missing Inspect source header")
    records = read_jsonl(results_path)
    summary = _score_summary(claim, records, header)
    summary["source_log_sha256"] = raw_hash
    summary["source_log_checked"] = source_log is not None
    return summary


def inspect_report_html(claim: dict[str, Any], summary: dict[str, Any]) -> str:
    """Render a standalone, fully escaped Inspect evidence report."""
    esc = lambda item: html.escape(str(item), quote=True)
    observed = summary["observed_score"]
    observed_text = f"{100 * observed:.1f}%" if observed is not None else "Unscored"
    coverage = f"{summary['distinct_tasks']}/{summary['total_tasks']} tasks · {summary['attempted']} attempted task-runs"
    ci = summary["task_cluster_bootstrap_95"]
    ci_text = f"{100*ci[0]:.1f}%–{100*ci[1]:.1f}%" if ci else "Unavailable for incomplete or unscored grid"
    issues = "".join(f"<li>{esc(msg)}</li>" for msg in summary["comparison_blockers"])
    rows = "".join(
        f"<tr><td><code>{esc(r['id'])[:16]}…</code></td><td>{r['epoch']}</td><td>{esc(r['status'])}</td></tr>"
        for r in summary["task_results"]
    )
    protocol = summary["reference_protocol_flags"]
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{esc(claim['title'])} — Evidence audit</title><style>
:root{{color-scheme:light;font-family:system-ui,-apple-system,sans-serif;background:#f9f8f3;color:#1d3229}}
*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:940px;margin:0 auto;padding:36px 24px 90px}}
header{{border-bottom:1px solid #d6dbd2;padding-bottom:24px;display:flex;justify-content:space-between;gap:20px;font-size:13px;font-weight:650}}
h1,h2{{font-family:Georgia,serif;font-weight:400;letter-spacing:-.03em}}h1{{font-size:clamp(34px,6vw,60px);line-height:1.1;max-width:780px}}
h2{{font-size:27px}}small,.secondary{{color:#607267}}.kicker{{font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:#547064;margin-top:60px}}
.metrics{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:30px 0}}.metric{{border:1px solid #d6dbd2;background:#fff;padding:24px}}
.metric span{{display:block;color:#607267;font-size:13px}}.metric strong{{display:block;font-size:clamp(28px,5vw,52px);letter-spacing:-.06em;margin-top:10px}}
section{{border-top:1px solid #d6dbd2;margin-top:34px;padding-top:22px}}p,li{{line-height:1.6}}ul{{padding-left:21px}}
.status{{border-left:3px solid #b17a3d;padding:16px;background:#eeece4}}table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid #d6dbd2;text-align:left;padding:12px 9px}}
th{{font-size:11px;text-transform:uppercase;letter-spacing:.09em}}code{{font-size:12px}}details{{margin-top:12px}}summary{{cursor:pointer}}
a{{color:inherit}}@media(max-width:600px){{.metrics{{grid-template-columns:1fr}}main{{padding:22px 16px}}}}
</style></head><body><main><header><strong>MCR / SOURCE EVIDENCE</strong><span>Offline · Self-reported Inspect log</span></header>
<div class="kicker">Published claim · Imported evidence</div><h1>{esc(claim['title'])}</h1>
<p class="secondary">Publisher source <a href="{esc(claim['source']['url'])}" rel="noopener noreferrer">{esc(claim['source']['url'])}</a><br>Logged model {esc(summary['model'])}</p>
<div class="metrics"><div class="metric"><span>Publisher-reported</span><strong>{100*claim['reported_score']:.1f}%</strong><small>Not independently confirmed</small></div>
<div class="metric"><span>Imported scored outcomes</span><strong>{esc(observed_text)}</strong><small>{esc(coverage)}</small></div></div>
<section><h2>What this establishes</h2><p class="status">{esc(summary['comparison_status'])} · An imported log is not an authenticated reproduction</p>
<p>{esc(summary['comparison_explanation'])}</p><ul>{issues}</ul></section>
<section><h2>Score accounting</h2><p>{summary['successes']} passed · {summary['failures']} failed · {summary['errors']} errors · {summary['unscored']} unscored.
{esc(coverage)}. Coverage complete: {esc(summary['coverage_complete'])}.
Logged input-and-target fingerprints: {summary['content_fingerprinted']}/{summary['attempted']}.</p>
<p>Task-resampling bootstrap interval: <strong>{esc(ci_text)}</strong>. {esc(summary['task_cluster_bootstrap_note'])}</p></section>
<section><h2>Logged protocol</h2><p>Judge: {esc(protocol.get('judge_recorded'))} · Dataset: {esc(protocol.get('dataset_recorded'))}<br>
Harness commit: {esc(protocol.get('harness_revision_recorded'))} · Inspect version: {esc(protocol.get('inspect_version_recorded'))}<br>
Recorded Inspect accuracy/mean: {esc(protocol.get('logged_mean'))}</p></section>
<section><h2>Local integrity</h2><p>Source Inspect log SHA-256: <code>{esc(summary['source_log_sha256'])}</code></p>
<p>The digest links this report to source bytes; it does not authenticate who executed the model or judge. This export deliberately omits prompts, images, gold answers, model responses and judge explanations. Respect the original dataset license.</p></section>
<section><h2>Task/epoch outcomes</h2><details><summary>Inspect {len(summary['task_results'])} pseudonymous records</summary>
<table><thead><tr><th>Task digest prefix</th><th>Epoch</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></details></section>
<footer><p><small>Model Claim Replay · Offline evidence report · No external scripts or trackers</small></p></footer>
</main></body></html>'''
