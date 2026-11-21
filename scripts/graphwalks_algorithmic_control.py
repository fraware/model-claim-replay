"""Evaluate a non-LLM BFS control against the pinned public GraphWalks cohort.

This is an explicit graph-algorithm control, not a reproduction of a model
benchmark claim. Predictions depend solely on the original prompt; reference
answers are used only after predictions have been computed. No model or API
access is needed. Original prompts, reference answers, and raw predictions
are never included in exported receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

from model_claim_replay.graphwalks import grade_response
from model_claim_replay.graphwalks_runtime import (
    DATASET_REVISION, DATASET_SHA256, INDEX_SHA256, verified_prompts,
)
from model_claim_replay.core import ReplayError, canonical_json, read_jsonl

# Parse only isolated edge lines, never prose, instructions or worked examples.
EXAMPLE = re.compile(r"<begin example>.*?<end example>", re.IGNORECASE | re.DOTALL)
EDGE = re.compile(r"^\s*([A-Za-z0-9_]{1,64})\s*->\s*([A-Za-z0-9_]{1,64})\s*$", re.MULTILINE)
OPERATION = re.compile(
    r"^\s*Perform a BFS from node ([A-Za-z0-9_]{1,64})"
    r"(?: with depth (\d+)\.| and return only the nodes at exactly depth (\d+)"
    r" \(not nodes at intermediate depths\)\.)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
GRAPH_HEADER = "The graph has the following edges:"


def solve_bfs_prompt(prompt: str) -> tuple[str, dict[str, int]]:
    """Compute graph-reachable nodes at exact BFS depth with no revisits.

    Input: a canonical GraphWalks public user prompt. The only information
    consulted is the prompt itself. A mismatch in structure is a parse failure
    and must never be silently guessed from the source answer.
    """
    if not isinstance(prompt, str) or not prompt:
        raise ReplayError("Missing benchmark prompt")
    source = EXAMPLE.sub("", prompt)
    header_positions = list(re.finditer(re.escape(GRAPH_HEADER), source, re.IGNORECASE))
    if len(header_positions) != 1:
        raise ReplayError("Ambiguous or missing graph-edge section")
    operation = list(OPERATION.finditer(source))
    if len(operation) != 1:
        # Include only a standardized diagnostic line; hexadecimal node IDs
        # are redacted so public reports never disclose raw prompts.
        candidates = [line.strip() for line in source.splitlines()
                      if line.strip().lower().startswith("perform a bfs")]
        template = re.sub(r"\b[0-9a-f]{10}\b", "<NODE>", candidates[-1]) if candidates else "missing"
        raise ReplayError("Unsupported BFS operation form: " + template[:180])
    start, legacy_depth, corrected_depth = operation[0].groups()
    depth = int(legacy_depth or corrected_depth)
    if depth > 100:
        raise ReplayError("Unreasonably deep BFS operation")
    if operation[0].start() <= header_positions[0].end():
        raise ReplayError("BFS operation precedes graph edges")
    graph_block = source[header_positions[0].end(): operation[0].start()]
    edges = EDGE.findall(graph_block)
    if not edges:
        raise ReplayError("No directed graph edges found")
    # Every nonempty graph line must be a valid edge, except headings that
    # introduce the operation. This guards against parsing a partial graph.
    for line in graph_block.splitlines():
        trimmed = line.strip()
        if trimmed and not EDGE.fullmatch(trimmed) and trimmed != "Operation:":
            raise ReplayError("Unexpected text inside graph-edge section")
    graph: dict[str, set[str]] = defaultdict(set)
    nodes: set[str] = set()
    for u, v in edges:
        graph[u].add(v)
        nodes.update((u, v))
    if start not in nodes:
        raise ReplayError("BFS starting node absent from parsed graph")
    visited = {start}
    frontier = {start}
    for _ in range(depth):
        following = set().union(*(graph.get(node, ()) for node in frontier)) - visited
        visited.update(following)
        frontier = following
    # Sort only for deterministic formatting; original grader checks a set.
    response = "Final Answer: [" + ", ".join(sorted(frontier)) + "]"
    return response, {"edge_count": len(edges), "node_count": len(nodes), "depth": depth}


def evaluate_control(index_path: Path, prompts: dict[str, str]) -> dict[str, Any]:
    """Score prompt-only algorithmic predictions against pinned answers."""
    index = read_jsonl(index_path)
    if len(index) != 200 or len(prompts) != 200:
        raise ReplayError("Expected exactly 200 pinned BFS prompts")
    outcomes = []
    total_f1 = 0.0
    failures = 0
    evaluated = 0
    by_band = {"short": [], "long": []}
    for position, row in enumerate(index):
        ident = row["id"]
        prompt = prompts.get(ident)
        if not isinstance(prompt, str):
            raise ReplayError("Missing pinned source task")
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if digest != row["prompt_sha256"]:
            raise ReplayError("Prompt hash and BFS index disagree")
        band = "short" if position < 100 else "long"
        record: dict[str, Any] = {"id": ident, "prompt_sha256": digest, "band": band}
        try:
            answer, metadata = solve_bfs_prompt(prompt)
        except ReplayError as exc:
            failures += 1
            record.update({"status": "parse_failed", "failure_reason": str(exc)})
        else:
            # Critical trust boundary: ground truth is only accessed here,
            # after the independent algorithm has produced its response.
            grade = grade_response(answer, row["answer_nodes"])
            total_f1 += grade["f1"]
            evaluated += 1
            by_band[band].append(grade["f1"])
            record.update({"status": "graded", "f1": grade["f1"], **metadata})
        outcomes.append(record)
    return {
        "schema_version": "graphwalks-algorithmic-control-v1",
        "evaluation_type": "explicit_graph_parser_and_bfs_no_model",
        "comparison_status": "not_comparable_to_gemini_model_claim",
        "candidate_dataset_revision": DATASET_REVISION,
        "source_parquet_sha256": DATASET_SHA256,
        "reference_index_sha256": INDEX_SHA256,
        "source_task_count": len(index),
        "graded": evaluated,
        "parse_failures": failures,
        "mean_f1_full_cohort": total_f1 / 200 if evaluated == 200 else None,
        "mean_f1_grading_subset_diagnostic": total_f1 / evaluated if evaluated else None,
        "mean_f1_by_band_full_coverage": {
            band: sum(vals) / 100 if len(vals) == 100 else None
            for band, vals in by_band.items()
        },
        "limitations": [
            "This control runs a specialized deterministic algorithm, not an AI model.",
            "It reads the full graph from each prompt and is not comparable to Gemini inference.",
            "The public dataset revision may differ from Google's internal benchmark revision.",
            "Original prompts, outputs and reference node lists are withheld from this artifact.",
            "Parsing failures prevent publication of a full-cohort mean.",
        ],
        "tasks": outcomes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Refusing to overwrite prior evidence")
    prompts = verified_prompts(args.parquet, args.index)
    report = evaluate_control(args.index, prompts)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("xb") as stream:
        stream.write(canonical_json(report) + b"\n")
    print("Algorithmic control only (not a model evaluation)")
    print("Parsed:", report["graded"], "of", report["source_task_count"])
    print("Failures:", report["parse_failures"])
    print("Complete-cohort F1:", report["mean_f1_full_cohort"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())