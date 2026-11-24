"""Source-bound token counting for the prespecified 16-task OpenAI campaign.

No generation endpoint is reachable through the production transport. Count
errors are recorded separately from measured context exclusions; no substitution,
truncation, automatic retry, score, or spending authorization is introduced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from model_claim_replay.core import ReplayError, canonical_json, read_jsonl, sha256_bytes
from model_claim_replay.graphwalks_runtime import (
    DATASET_REVISION, DATASET_SHA256, INDEX_SHA256, verified_prompts,
)
from model_claim_replay.openai_graphwalks import (
    MODEL, TASK, INPUT_LIMIT, CONTEXT_LIMIT, OUTPUT_LIMIT,
    INPUT_RATE, OUTPUT_RATE, choose_key, reservation,
)
from openai_graphwalks_preflight import count_only_request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evidence/graphwalks/openai-campaign-v1.json"
PREFIX = "model-claim-replay/openai-graphwalks-campaign-v1/2026-11-24:"
CEILING = Decimal("100")


def selected_tasks(index: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reproduce the frozen hash ordering from the pinned source index."""
    if len(index) != 200 or len({r["id"] for r in index}) != 200:
        raise ReplayError("Expected 200 unique pinned BFS records")
    groups: dict[str, list[dict[str, Any]]] = {"short": [], "long": []}
    for row in index:
        size = row.get("prompt_chars_actual")
        if type(size) is not int or size <= 0:
            raise ReplayError("Invalid source prompt length")
        band = "short" if size < 1_000_000 else "long"
        groups[band].append({"id": row["id"], "prompt_chars": size,
                             "prompt_sha256": row["prompt_sha256"], "band": band})
    if any(len(rows) != 100 for rows in groups.values()) or TASK not in {r["id"] for r in groups["short"]}:
        raise ReplayError("Unexpected source strata or pilot identity")
    return [
        row
        for band in ("short", "long")
        for row in sorted(
            (r for r in groups[band] if r["id"] != TASK),
            key=lambda r: hashlib.sha256((PREFIX + r["id"]).encode()).hexdigest(),
        )[:8]
    ]


def validate_manifest(manifest: dict[str, Any], index: list[dict[str, Any]]) -> None:
    expected = {
        "schema_version": "graphwalks-openai-campaign-v1", "protocol_issue": 42,
        "selection_prefix": PREFIX, "excluded_pilot": TASK,
        "source_dataset_revision": DATASET_REVISION,
        "source_parquet_sha256": DATASET_SHA256, "reference_index_sha256": INDEX_SHA256,
        "model": MODEL, "max_output_tokens": OUTPUT_LIMIT,
        "input_limit": INPUT_LIMIT, "context_limit": CONTEXT_LIMIT,
        "planning_ceiling_usd": str(CEILING),
        "input_usd_per_million_upper": str(INPUT_RATE),
        "output_usd_per_million_upper": str(OUTPUT_RATE),
        "tasks": selected_tasks(index),
    }
    if manifest != expected:
        raise ReplayError("Manifest does not reproduce prespecified cohort and protocol")


def count_campaign(manifest: dict[str, Any], prompts: dict[str, str], *,
                   key: str, request: Callable = count_only_request) -> dict[str, Any]:
    """Count all 16 original inputs once; record every outcome, even errors."""
    for task in manifest["tasks"]:
        prompt = prompts.get(task["id"])
        if (not isinstance(prompt, str) or len(prompt) != task["prompt_chars"]
                or sha256_bytes(prompt.encode()) != task["prompt_sha256"]):
            raise ReplayError("Selected prompt differs from frozen source commitment")
    rows = []
    for task in manifest["tasks"]:
        row = {**task, "input_tokens": None, "reservation_usd": None,
               "status": "count_failed"}
        try:
            counted = request("/v1/responses/input_tokens", {
                "model": MODEL, "input": prompts[task["id"]],
                "reasoning": {"effort": "xhigh"}, "truncation": "disabled",
            }, key)
            n = counted.get("input_tokens")
            if counted.get("object") != "response.input_tokens" or type(n) is not int or n <= 0:
                raise ReplayError("Invalid input-token response")
            row["input_tokens"] = n
            fits = n <= INPUT_LIMIT and n + OUTPUT_LIMIT <= CONTEXT_LIMIT
            row["status"] = "feasible" if fits else "context_blocked"
            if fits:
                row["reservation_usd"] = str(reservation(n, OUTPUT_LIMIT))
        except ReplayError as exc:
            # Only allowlisted transport classifications, never error bodies.
            msg = str(exc)
            row["count_error"] = msg if msg in {
                "Invalid input-token response", "OpenAI transport or response decoding failed",
                "OpenAI response exceeded byte bound", "Unexpected OpenAI response object",
            } or (msg.startswith("OpenAI HTTP ") and len(msg) == 15 and msg[-3:].isdigit()) else "provider_count_failed"
        rows.append(row)
    totals = Counter(row["status"] for row in rows)
    total = sum((Decimal(row["reservation_usd"]) for row in rows
                 if row["reservation_usd"] is not None), Decimal(0))
    return {
        "schema_version": "graphwalks-openai-campaign-preflight-v1",
        "model": MODEL, "protocol_issue": 42, "selected_tasks": len(rows),
        "feasible": totals["feasible"], "context_blocked": totals["context_blocked"],
        "count_failed": totals["count_failed"], "total_feasible_reservation_usd": str(total),
        "planning_ceiling_usd": str(CEILING),
        "within_planning_ceiling": total <= CEILING,
        "all_counts_observed": totals["count_failed"] == 0,
        "generation_performed": False, "paid_authorization": False,
        "published_claim_reproduced": False, "tasks": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        prompts = verified_prompts(args.parquet, args.index)
        manifest = json.loads(MANIFEST.read_bytes())
        validate_manifest(manifest, read_jsonl(args.index))
        key = choose_key(dict(os.environ), count_only_request)
        report = count_campaign(manifest, prompts, key=key)
        report["manifest_sha256"] = sha256_bytes(MANIFEST.read_bytes())
        report["reference_index_sha256"] = INDEX_SHA256
        with args.out.open("xb") as stream:
            stream.write(canonical_json(report) + b"\n")
    except (ReplayError, OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"Campaign preflight failed: {exc}\n")
    print(json.dumps({k: v for k, v in report.items() if k != "tasks"}, sort_keys=True))
    for row in report["tasks"]:
        print(json.dumps(row, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
