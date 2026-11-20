"""Paired, task-clustered comparison of two imported Inspect evidence bundles.

This is a diagnostic comparison of locally supplied logs, not independent
provider authentication and never a certification of a publisher's benchmark
claim. Comparing disjoint tasks, epochs, or grader configurations is refused.
"""

from __future__ import annotations

import html
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from .core import ReplayError, read_bytes, read_jsonl
from .inspect_evidence import verify_inspect_bundle


_PROTOCOL_FIELDS = (
    "task", "judge_model", "dataset_repo", "dataset_split",
    "requested_epochs", "harness_revision", "harness_dirty", "inspect_version",
)


def _validated_bundle(
    claim_path: Path, run_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[tuple[str, int], int], dict[tuple[str, int], str | None]]:
    """Load a verified import; create a task/epoch score map without raw content."""
    summary = verify_inspect_bundle(claim_path, run_dir)
    metadata = json.loads(read_bytes(run_dir / "run.json"))
    header = metadata["inspect_header"]
    rows = read_jsonl(run_dir / "results.jsonl")
    scores = {
        (row["task_key"], row["epoch"]): row["score"]
        for row in rows if row["status"] in ("pass", "fail")
    }
    fingerprints = {
        (row["task_key"], row["epoch"]): row.get("content_sha256")
        for row in rows if row["status"] in ("pass", "fail")
    }
    return summary, header, scores, fingerprints


def compare_inspect_bundles(
    claim_path: Path, left: Path, right: Path,
    *, bootstrap_draws: int = 5000, seed: int = 20261120,
) -> dict[str, Any]:
    """Compare two inspected logs over exactly matching scored task/epoch pairs.

    The resampling unit is a *task*, preserving its repeated epochs. Bootstrap
    quantiles are exploratory descriptions of the curated task set; neither a
    population confidence guarantee nor a test of a publisher's headline score.
    """
    if bootstrap_draws < 100 or bootstrap_draws > 100_000:
        raise ReplayError("Bootstrap draws must be in [100, 100000]")
    left_summary, left_header, left_scores, left_fingerprints = _validated_bundle(claim_path, left)
    right_summary, right_header, right_scores, right_fingerprints = _validated_bundle(claim_path, right)
    blockers: list[str] = []

    # Tasks must be *exactly* paired; computing an intersection-only estimate
    # would silently select a potentially easier or harder subset.
    if set(left_scores) != set(right_scores):
        blockers.append("Scored task/epoch sets differ: intersection-only comparisons are disallowed")
    if left_summary["assessed"] != left_summary["attempted"] or right_summary["assessed"] != right_summary["attempted"]:
        blockers.append("One or both runs have errored or unscored records")
    if left_summary["attempted"] != right_summary["attempted"]:
        blockers.append("The runs have different attempted task/epoch counts")
    if not left_scores or not right_scores:
        blockers.append("No scored samples are available for comparison")
    if any(digest is None for digest in (*left_fingerprints.values(), *right_fingerprints.values())):
        blockers.append(
            "Unpinned chart content: both runs need image-byte and answer fingerprints "
            "for every scored task/epoch"
        )
    elif left_fingerprints != right_fingerprints:
        blockers.append(
            "Chart inputs or reference answers differ across runs despite matching task IDs"
        )
    for field in _PROTOCOL_FIELDS:
        lval, rval = left_header.get(field), right_header.get(field)
        if lval != rval:
            blockers.append(f"Logged protocol differs at {field}")
        elif lval is None:
            blockers.append(f"Logged protocol is unspecified at {field}")
    if left_header.get("harness_dirty") is not False or right_header.get("harness_dirty") is not False:
        blockers.append("Clean, pinned harness provenance is not established for both runs")
    # Unequal per-task repeat counts would turn the comparison into an
    # undocumented weighting scheme, even with identical scored-ID sets.
    requested_epochs = left_header.get("requested_epochs")
    if type(requested_epochs) is int and requested_epochs > 0:
        task_epochs: dict[str, set[int]] = defaultdict(set)
        for task_key, epoch in left_scores:
            task_epochs[task_key].add(epoch)
        if any(epochs != set(range(1, requested_epochs + 1)) for epochs in task_epochs.values()):
            blockers.append("Incomplete or irregular per-task epoch coverage in the paired observations")
    if left_summary["source_log_sha256"] == right_summary["source_log_sha256"]:
        blockers.append("Both bundles refer to the same original source log")
    # Results stay explicitly non-attested even if every recorded setting matches.
    result: dict[str, Any] = {
        "schema_version": "paired-inspect-v1",
        "claim_id": left_summary["claim_id"],
        "status": "blocked" if blockers else "paired_diagnostic_only",
        "interpretation": (
            "The source logs are self-reported. A paired within-dataset difference does not "
            "authenticate model execution, prove source-protocol equivalence, or reproduce "
            "the publisher's claim."
        ),
        "left": {"model": left_summary["model"], "score": left_summary["observed_score"],
                 "assessed": left_summary["assessed"], "source_log_sha256": left_summary["source_log_sha256"]},
        "right": {"model": right_summary["model"], "score": right_summary["observed_score"],
                  "assessed": right_summary["assessed"], "source_log_sha256": right_summary["source_log_sha256"]},
        "protocol_match": not blockers,
        "blockers": blockers,
        "paired_samples": 0,
        "paired_tasks": 0,
        "delta_right_minus_left_pp": None,
        "task_cluster_bootstrap_95_pp": None,
        "interval_note": (
            "Percentile task-cluster bootstrap, with epochs retained inside each task. "
            "Descriptive only for the selected tasks and run conditions, not a "
            "population-confidence interval or significance test."
        ),
        "covers_reference_grid": (left_summary["coverage_complete"] and right_summary["coverage_complete"]),
    }
    if blockers:
        return result

    by_task: dict[str, list[float]] = defaultdict(list)
    for task_epoch in sorted(left_scores):
        key, _ = task_epoch
        by_task[key].append(right_scores[task_epoch] - left_scores[task_epoch])
    task_deltas = [sum(changes) / len(changes) for changes in by_task.values()]
    result["paired_samples"] = len(left_scores)
    result["paired_tasks"] = len(by_task)
    result["delta_right_minus_left_pp"] = 100.0 * sum(task_deltas) / len(task_deltas)
    if len(task_deltas) >= 2:
        rng = random.Random(seed)
        n = len(task_deltas)
        draws = sorted(100 * sum(task_deltas[rng.randrange(n)] for _ in range(n)) / n
                       for _ in range(bootstrap_draws))
        low = draws[int(bootstrap_draws * 0.025)]
        high = draws[min(bootstrap_draws - 1, int(bootstrap_draws * 0.975))]
        result["task_cluster_bootstrap_95_pp"] = [low, high]
    return result


def compare_report_html(report: dict[str, Any]) -> str:
    """Generate an offline, script-free report from validated comparison metadata."""
    esc = lambda x: html.escape(str(x), quote=True)
    delta = report["delta_right_minus_left_pp"]
    interval = report["task_cluster_bootstrap_95_pp"]
    shown_delta = f"{delta:+.2f} pp" if delta is not None else "Blocked"
    shown_interval = (f"[{interval[0]:+.2f}, {interval[1]:+.2f}] pp" if interval else "Not available")
    issues = "".join(f"<li>{esc(s)}</li>" for s in report["blockers"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>Model Claim Replay · Paired inspection</title>
<style>:root{{font-family:system-ui,sans-serif;color:#173127;background:#f8f7f1}}
*{{box-sizing:border-box}}main{{max-width:850px;margin:auto;padding:36px 22px 90px}}
h1{{font:normal clamp(32px,6vw,60px) Georgia,serif;letter-spacing:-.04em}}
small,.muted{{color:#5c7065}}section{{border-top:1px solid #ccd5cc;margin-top:30px;padding-top:18px}}
li,p{{line-height:1.6}}.metrics{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
article{{background:white;border:1px solid #d9ded7;padding:20px;min-width:0;overflow-wrap:anywhere}}strong{{font-size:28px;display:block;margin:10px 0}}
.notice{{padding:15px;background:#eeeadb;border-left:4px solid #9b793a}}
@media(max-width:600px){{.metrics{{grid-template-columns:1fr}}}}</style></head><body><main>
<small>MODEL CLAIM REPLAY / PAIRED AUDIT</small><h1>Compare the evidence.</h1>
<p class="notice">{esc(report['status'])}. {esc(report['interpretation'])}</p>
<div class="metrics"><article><small>Left · {esc(report['left']['model'])}</small><strong>{esc('Unscored' if report['left']['score'] is None else f"{100*report['left']['score']:.2f}%")}</strong><small>Source log SHA-256: {esc(report['left']['source_log_sha256'])}</small></article>
<article><small>Right · {esc(report['right']['model'])}</small><strong>{esc('Unscored' if report['right']['score'] is None else f"{100*report['right']['score']:.2f}%")}</strong><small>Source log SHA-256: {esc(report['right']['source_log_sha256'])}</small></article></div>
<section><h2>Paired difference</h2><strong>{esc(shown_delta)}</strong>
<p>Right minus left, in percentage points. {report['paired_tasks']} matched tasks and {report['paired_samples']} task-epochs.
Full reference grid: {esc(report['covers_reference_grid'])}.</p>
<p>Exploratory 95% task-cluster bootstrap: {esc(shown_interval)}.</p>
<p class="muted">{esc(report['interval_note'])}</p></section>
<section><h2>Comparison blockers</h2><ul>{issues if issues else '<li>No additional within-run matching blockers; source-provenance limitations still apply.</li>'}</ul></section>
<footer><small>Offline HTML · No external scripts · Recompute from source evidence with the CLI</small></footer>
</main></body></html>'''
