"""Offline implementation of the published GraphWalks answer parser and F1 rule.

Scoring only consumes an explicit, independently prepared BFS reference index
and recorded responses. It does not load the original Parquet dataset, call a
model, or assert equivalence to a vendor's published evaluation.

Source rule: https://huggingface.co/datasets/openai/graphwalks/blob/main/README.md
The dataset card is MIT-licensed. Preserve its source revision separately.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .core import ReplayError, read_bytes, read_jsonl, sha256_bytes

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_NODE_LIST = re.compile(r"\[.*\]")


def extract_nodes(response: str) -> tuple[set[str], bool]:
    """Match the dataset card's last-line `Final Answer: [a, b]` parser.

    The reference checks the *final line*, looks for the exact marker, and
    searches that line for a bracketed list. A final newline intentionally
    makes that last line empty. Duplicate IDs collapse to a set for F1.

    Returns (nodes, failed_to_parse). The parser is deliberately permissive
    about the marker's position to reproduce the benchmark code's semantics.
    """
    if not isinstance(response, str):
        raise ReplayError("GraphWalks response must be text")
    line = response.split("\n")[-1]
    if "Final Answer:" not in line:
        return set(), True
    found = _NODE_LIST.search(line)
    if found is None:
        return set(), True
    nodes = {entry.strip() for entry in found.group(0).strip("[]").split(",")
             if entry.strip()}
    return nodes, False


def grade_response(response: str, answer_nodes: list[str]) -> dict[str, Any]:
    """Compute OpenAI's set-overlap F1, preserving malformed/empty behavior.

    Malformed output yields F1=0 even for an empty ground truth. Properly
    formatted empty predictions and an empty reference yield F1=1.
    """
    if not isinstance(answer_nodes, list) or any(
        not isinstance(item, str) or not item for item in answer_nodes
    ):
        raise ReplayError("GraphWalks reference answer must be a list of nonempty node IDs")
    predicted, parse_failed = extract_nodes(response)
    truth = set(answer_nodes)
    if parse_failed:
        precision = recall = f1 = 0.0
    elif not truth and not predicted:
        precision = recall = f1 = 1.0
    else:
        overlap = len(predicted & truth)
        precision = overlap / len(predicted) if predicted else 0.0
        recall = overlap / len(truth) if truth else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "f1": f1,
        "precision": precision,
        "recall": recall,
        "parse_failed": parse_failed,
        "predicted_nodes": len(predicted),
        "reference_nodes": len(truth),
    }


def score_recorded_bfs(
    task_index: Path, response_file: Path, *, expected_index_sha256: str,
    dataset_revision: str,
) -> dict[str, Any]:
    """Score one locally recorded BFS response per task, without publishing raw text.

    `task_index` contains ID, problem_type=bfs and answer_nodes; it is a
    separately prepared reference index, not a validated original data dump.
    The expected index digest is an explicit check against accidental changes.

    An API error or missing response is distinct from a malformed model answer;
    no full-cohort score is emitted in the former cases. The result never claims
    source protocol equivalence or independent model provenance.
    """
    if not isinstance(expected_index_sha256, str) or not _SHA64.fullmatch(expected_index_sha256):
        raise ReplayError("--index-sha256 must be a lowercase 64-character SHA-256")
    if not isinstance(dataset_revision, str) or not _SHA40.fullmatch(dataset_revision):
        raise ReplayError("--dataset-revision must be a 40-character lowercase commit SHA")
    if sha256_bytes(read_bytes(task_index)) != expected_index_sha256:
        raise ReplayError("Reference index bytes do not match --index-sha256")
    tasks = read_jsonl(task_index)
    results = read_jsonl(response_file)
    by_id = {row["id"]: row for row in results}
    task_ids = {row["id"] for row in tasks}
    unknown = set(by_id) - task_ids
    if unknown:
        raise ReplayError("Response log contains IDs absent from the reference index")
    rows: list[dict[str, Any]] = []
    total = parsed = score_count = error_count = missing = 0
    sum_f1 = 0.0
    for item in tasks:
        if item.get("problem_type") != "bfs":
            raise ReplayError("Reference index contains a non-BFS problem")
        answer = item.get("answer_nodes")
        if not isinstance(answer, list) or any(
            not isinstance(x, str) or not x for x in answer
        ):
            raise ReplayError("Reference index has invalid answer_nodes")
        ident = item["id"]
        result = by_id.get(ident)
        row: dict[str, Any] = {"id": ident}
        if result is None:
            row["status"] = "missing"
            missing += 1
        elif result.get("status") == "error" and "output" not in result:
            row["status"] = "error"
            error_count += 1
        elif result.get("status") == "ok" and isinstance(result.get("output"), str):
            grade = grade_response(result["output"], answer)
            row.update({"status": "graded", **grade})
            parsed += int(not grade["parse_failed"])
            score_count += 1
            sum_f1 += grade["f1"]
        else:
            raise ReplayError("Response status must be ok with text or error without output")
        rows.append(row)
        total += 1
    complete = score_count == total
    return {
        "schema_version": "graphwalks-offline-grade-v1",
        "evidence_level": "locally_imported_response_scores_unattested",
        "dataset_revision_user_declared": dataset_revision,
        "reference_index_sha256": expected_index_sha256,
        "response_file_sha256": sha256_bytes(read_bytes(response_file)),
        "task_count": total,
        "graded": score_count,
        "parsed": parsed,
        "malformed": score_count - parsed,
        "api_errors": error_count,
        "missing": missing,
        "mean_f1": sum_f1 / total if complete else None,
        "scored_subset_mean_f1_diagnostic": sum_f1 / score_count if score_count else None,
        "comparison_status": "not_comparable",
        "comparison_explanation": (
            "Local parsing and F1 only. The evaluator did not verify input prompts, "
            "source dataset bytes, model execution, the publisher's selected 200 items, "
            "or its complete API and sampling settings."
        ),
        "results": rows,
    }


def save_scoring_report(report: dict[str, Any], output: Path) -> None:
    """Write a new JSON artifact atomically; never overwrite prior evidence."""
    if output.exists():
        raise ReplayError(f"Output path already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".graphwalks-", suffix=".json", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        os.link(temporary, output)  # Atomic, no-overwrite creation on local filesystems.
    finally:
        Path(temporary).unlink(missing_ok=True)
